"""SSE streaming, chat, action, and voice routes."""

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from src.api.shared import chat_rate_limiter, token_broadcaster


def _get_busy_lock():
    """Get or create the app-level busy lock, ensuring it's set once."""
    lock = getattr(current_app, "_busy_lock", None)
    if lock is None:
        lock = threading.Lock()
        current_app._busy_lock = lock
    return lock


def _run_with_app_context(app, func):
    with app.app_context():
        func()

logger = logging.getLogger(__name__)

streaming_bp = Blueprint("streaming", __name__)


@streaming_bp.route("/")
def index():
    return render_template("index.html")


@streaming_bp.route("/stream")
def stream():
    query     = request.args.get("query", "").strip()
    domain    = request.args.get("domain", "").strip() or None
    is_voice  = request.args.get("voice", "").lower() in ("1", "true")
    client_id = request.args.get("client_id", f"client_{int(time.time())}")
    mode      = request.args.get("mode", "fast")
    reasoning = request.args.get("reasoning", "0").lower() in ("1", "true")

    transform_voice_prompt = None
    voice_transform = False
    if is_voice:
        try:
            from src.voice.prompt_transformer import transform as transform_voice_prompt
            voice_transform = True
        except ImportError:
            pass

    if is_voice and voice_transform and transform_voice_prompt:
        result = transform_voice_prompt(query)
        query = result.cleaned or query

    if not query:
        return Response(
            f"data: {json.dumps({'type': 'error', 'text': 'No query provided'})}\n\n",
            mimetype="text/event-stream",
        )

    if len(query) > 10000:
        return Response(
            f"data: {json.dumps({'type': 'error', 'text': 'Query too long (max 10000 chars)'})}\n\n",
            mimetype="text/event-stream",
        )

    q = token_broadcaster.register(client_id)
    if q is None:
        return Response(
            f"data: {json.dumps({'type': 'error', 'text': 'Too many active connections'})}\n\n",
            mimetype="text/event-stream",
        )

    if query.startswith("/"):
        # Slash commands go through the dispatcher (supervisor shim handles them)
        from src.api.dispatcher import dispatch

        def run_cmd():
            try:
                sup = getattr(current_app, "supervisor", None)
                if not sup:
                    q.put(("error", "System not ready."))
                    return
                try:
                    dispatch(query, domain=domain, sup=sup, orch=None)
                except Exception as e:
                    logger.warning("[SSE] Command error for %s: %s", client_id, e)
                q.put(("done", {"sentiment": 0.0, "specialist": None}))
            except Exception as e:
                logger.warning("[SSE] Fatal command error: %s", e)
                q.put(("error", "Command error"))

        app = current_app._get_current_object()
        threading.Thread(
            target=_run_with_app_context, args=(app, run_cmd), daemon=True
        ).start()
    else:
        # Natural language → web orchestrator (direct LLM streaming, no CoreOrchestrator)
        from src.api.web_orchestrator import stream_response

        def run_nl():
            try:
                stream_response(query, client_id, mode=mode, reasoning=reasoning)
                q.put(("done", {"sentiment": 0.0, "specialist": None}))
            except Exception as e:
                logger.error("[SSE] WebOrchestrator error for %s: %s", client_id, e)
                q.put(("error", "LLM error — check server logs"))

        threading.Thread(target=run_nl, daemon=True).start()

    def generate():
        connection_start = time.time()
        last_activity = time.time()
        heartbeat_interval = 30

        try:
            while True:
                try:
                    now = time.time()
                    if now - connection_start > 600:
                        logger.debug(f"[SSE] {client_id} absolute timeout")
                        break

                    timeout = min(
                        30, max(5, heartbeat_interval - (now - last_activity))
                    )
                    kind, text = q.get(timeout=timeout)
                    last_activity = now

                    if not isinstance(text, (str, dict)):
                        text = str(text)

                    payload = json.dumps(
                        {
                            "type": kind,
                            "text": text,
                            "timestamp": now,
                            "client_id": client_id,
                        }
                    )
                    yield f"data: {payload}\n\n"

                    if kind in ("done", "error"):
                        logger.debug(f"[SSE] Stream completed for {client_id} ({kind})")
                        break

                except __import__("queue").Empty:
                    now = time.time()
                    if now - last_activity > heartbeat_interval:
                        status = "processing" if q.qsize() > 0 else "waiting"
                        heartbeat = {
                            "type": "heartbeat",
                            "timestamp": now,
                            "status": status,
                            "queue_size": q.qsize(),
                        }
                        yield f"data: {json.dumps(heartbeat)}\n\n"
                        last_activity = now

        except GeneratorExit:
            logger.debug(f"[SSE] {client_id} disconnected gracefully")
        except Exception as e:
            logger.debug(f"[SSE] Stream error for {client_id}: {e}")
            try:
                error_payload = json.dumps(
                    {
                        "type": "error",
                        "text": "Stream interrupted",
                        "timestamp": time.time(),
                    }
                )
                yield f"data: {error_payload}\n\n"
            except Exception:
                pass
        finally:
            token_broadcaster.unregister(client_id)
            logger.debug(
                f"[SSE] Cleaned up {client_id} (duration: {time.time() - connection_start:.1f}s)"
            )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@streaming_bp.route("/chat", methods=["POST"])
def chat():
    if not chat_rate_limiter.is_allowed(request.remote_addr or "unknown"):
        return jsonify({"ok": False, "error": "Rate limited. Try again later."}), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid request format"}), 400

    message = data.get("message", "").strip()
    if not message:
        return jsonify({"ok": False})

    from src.api.dispatcher import dispatch
    sup = current_app.supervisor
    orch = current_app.orchestrator
    fallback = getattr(current_app, "web_llm", None)
    busy = getattr(current_app, "_busy_lock", None)

    def run():
        cancel = threading.Event()

        def run_chat():
            try:
                if busy:
                    with busy:
                        try:
                            dispatch(
                                message,
                                sup=sup,
                                orch=orch,
                                fallback_chat=fallback.chat if fallback else None,
                                fallback_stream=True,
                            )
                        except Exception as e:
                            token_broadcaster.broadcast("error", f"Error: {e}")
                        finally:
                            token_broadcaster.broadcast("done", "")
                else:
                    try:
                        dispatch(
                            message,
                            sup=sup,
                            orch=orch,
                            fallback_chat=fallback.chat if fallback else None,
                            fallback_stream=True,
                        )
                    except Exception as e:
                        token_broadcaster.broadcast("error", f"Error: {e}")
                    finally:
                        token_broadcaster.broadcast("done", "")
            finally:
                cancel.set()

        worker = threading.Thread(target=run_chat, daemon=True)
        worker.start()

        if not cancel.wait(timeout=120):
            token_broadcaster.broadcast("error", "Request timed out after 120s")

    app = current_app._get_current_object()
    threading.Thread(target=_run_with_app_context, args=(app, run), daemon=True).start()
    return jsonify({"ok": True})


@streaming_bp.route("/unified", methods=["POST"])
def unified():
    if not chat_rate_limiter.is_allowed(request.remote_addr or "unknown"):
        return jsonify({"ok": False, "error": "Rate limited. Try again later."}), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid request format"}), 400

    message = data.get("message", "").strip()
    if not message:
        return jsonify({"ok": False, "error": "No message provided"}), 400

    sup = current_app.supervisor
    def run():
        lock = _get_busy_lock()
        with lock:
            try:
                sup.handle_unified_request(message)
            except Exception as e:
                token_broadcaster.broadcast("error", f"Unified Error: {e}")
            finally:
                token_broadcaster.broadcast("done", "")

    app = current_app._get_current_object()
    threading.Thread(target=_run_with_app_context, args=(app, run), daemon=True).start()
    return jsonify({"ok": True})


@streaming_bp.route("/council", methods=["POST"])
def council():
    if not chat_rate_limiter.is_allowed(request.remote_addr or "unknown"):
        return jsonify({"error": "Rate limited. Try again later."}), 429

    busy_lock = _get_busy_lock()
    if busy_lock.locked():
        return jsonify({"error": "Busy..."}), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request format"}), 400

    query = data.get("query", "")
    if not query:
        return jsonify({"error": "No query"}), 400

    sup = current_app.supervisor

    def run_council():
        lock = busy_lock
        with lock:
            try:
                sup.assemble_council(query)
            except Exception as e:
                token_broadcaster.broadcast("error", f"Council Error: {e}")
            finally:
                token_broadcaster.broadcast("done", "")

    app = current_app._get_current_object()
    threading.Thread(target=_run_with_app_context, args=(app, run_council), daemon=True).start()
    return jsonify({"status": "Recruiting experts..."})


@streaming_bp.route("/brief", methods=["POST"])
def brief():
    sup = current_app.supervisor

    def run():
        lock = _get_busy_lock()
        with lock:
            try:
                sup.morning_brief()
            except Exception as e:
                token_broadcaster.broadcast("error", f"Brief Error: {e}")
            finally:
                token_broadcaster.broadcast("done", "")

    app = current_app._get_current_object()
    threading.Thread(target=_run_with_app_context, args=(app, run), daemon=True).start()
    return jsonify({"ok": True})


@streaming_bp.route("/optic", methods=["POST"])
def optic():
    sup = current_app.supervisor

    def run():
        lock = _get_busy_lock()
        with lock:
            try:
                sup.run("/optic")
            except Exception as e:
                token_broadcaster.broadcast("error", f"Optic Error: {e}")
            finally:
                token_broadcaster.broadcast("done", "")

    app = current_app._get_current_object()
    threading.Thread(target=_run_with_app_context, args=(app, run), daemon=True).start()
    return jsonify({"ok": True})


@streaming_bp.route("/horizon", methods=["POST"])
def horizon():
    sup = current_app.supervisor

    def run():
        lock = _get_busy_lock()
        with lock:
            try:
                sup.run("/horizon")
            except Exception as e:
                token_broadcaster.broadcast("error", f"Horizon Error: {e}")
            finally:
                token_broadcaster.broadcast("done", "")

    app = current_app._get_current_object()
    threading.Thread(target=_run_with_app_context, args=(app, run), daemon=True).start()
    return jsonify({"ok": True})


@streaming_bp.route("/interrupt", methods=["POST"])
def interrupt():
    try:
        from src.orchestrator.mcts_integration import get_dispatcher

        dispatcher = get_dispatcher()
        dispatcher.interrupt()

        token_broadcaster.broadcast("error", "Execution interrupted by user")
        token_broadcaster.broadcast("done", "")

        return jsonify({"ok": True, "message": "Tasks halted"})
    except Exception as e:
        logger.error("Interrupt error: %s", e)
        return jsonify({"ok": False, "error": "Failed to interrupt"}), 500


@streaming_bp.route("/api/mcts/state", methods=["GET"])
def mcts_state():
    try:
        from src.orchestrator.mcts_integration import get_dispatcher

        dispatcher = get_dispatcher()
        state = dispatcher.get_current_state()
        return jsonify(state)
    except Exception as e:
        logger.error("MCTS state error: %s", e)
        return jsonify({"error": "MCTS state unavailable"}), 500


@streaming_bp.route("/api/domains", methods=["GET"])
def api_domains():
    return jsonify(
        {
            "ok": True,
            "domains": [
                {"id": "chat", "label": "Chat"},
                {"id": "auto", "label": "Automotive"},
                {"id": "audio", "label": "Audio"},
                {"id": "fitness", "label": "Fitness"},
                {"id": "growth", "label": "Growth"},
                {"id": "code", "label": "Code"},
                {"id": "journal", "label": "Journal"},
            ],
        }
    )


@streaming_bp.route("/api/rlhf/options", methods=["POST"])
def api_rlhf_options():
    from dataclasses import asdict

    from src.eval.rlhf_collection import PreferenceCollector

    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    count = int(data.get("count") or 3)
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    collector = PreferenceCollector()
    try:
        options = collector.make_options(query, count=count)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify(
        {"ok": True, "query": query, "options": [asdict(option) for option in options]}
    )


@streaming_bp.route("/api/rlhf/preference", methods=["POST"])
def api_rlhf_preference():
    from src.eval.rlhf_collection import PreferenceCollector

    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    options = data.get("options") or []
    chosen_id = data.get("chosen_id")
    try:
        pairs = PreferenceCollector().store_preference(
            query=query,
            options=options,
            chosen_id=chosen_id,
            metadata=data.get("metadata") or {},
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "pairs_stored": len(pairs)})


@streaming_bp.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json() or {}
    feedback_dir = Path("data") / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.time(),
        "rating": data.get("rating"),
        "message_index": data.get("message_index"),
        "message": data.get("message", ""),
        "route_meta": data.get("route_meta") or {},
    }
    with (feedback_dir / "feedback.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True) + "\n")
    return jsonify({"ok": True})


@streaming_bp.route("/api/search", methods=["GET"])
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    try:
        sup = current_app.supervisor
        results = sup.pka_db.hybrid_search(query, limit=5)
        return jsonify(results)
    except Exception as e:
        logger.error("Search API error: %s", e)
        return jsonify({"error": "Search unavailable"}), 500


@streaming_bp.route("/api/journal", methods=["GET"])
def get_journal():
    try:
        from src.api.shared import get_pka_db
        pka_db = get_pka_db()
        if not pka_db:
            return jsonify([])
        return jsonify(pka_db.get_entries())
    except Exception as e:
        logger.error("Journal API error: %s", e)
        return jsonify([])


@streaming_bp.route("/api/chat_history/import", methods=["POST"])
def import_chat_history():
    data = request.json
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        from src.utils.chat_importer import ChatImporter

        sup = current_app.supervisor
        importer = ChatImporter()
        success = importer.import_raw_text(text)
        if success:
            threading.Thread(
                target=sup.profiler_engine.process_batch, args=(sup, 1), daemon=True
            ).start()
        return jsonify({"success": success})
    except Exception:
        logger.error("Chat history import error")
        return jsonify({"error": "Import failed"}), 500


@streaming_bp.route("/api/transcribe-legacy", methods=["POST"])
def api_transcribe():
    """Deprecated legacy transcription entrypoint."""
    from src.api.voice_routes import transcribe_audio

    return transcribe_audio()


@streaming_bp.route("/schematic/<project_id>")
def view_schematic(project_id):
    return render_template("schematic_viewer.html", project_id=project_id)


@streaming_bp.route("/api/schematic/<project_id>/overlay")
def get_schematic_overlay(project_id):
    from pathlib import Path as _Path

    from flask import Response as _Response

    from src.utils.path_security import PathSecurityError, safe_project_id

    try:
        project_id = safe_project_id(project_id)
    except PathSecurityError:
        return jsonify({"error": "Invalid project ID"}), 400
    try:
        from src.utils.duckdb_client import DuckDBClient
        from src.utils.schematic_analyzer import SchematicAnalyzer
        from src.utils.schematic_overlay import Component, SchematicOverlayGenerator

        db = DuckDBClient()
        analyzer = SchematicAnalyzer(db_client=db)
        component_dicts = analyzer.get_schematic_components(project_id)

        components = []
        for c in component_dicts:
            comp = Component(
                designator=c.get("designator", ""),
                type=c.get("type", "unknown"),
                x=c.get("x", 0),
                y=c.get("y", 0),
                width=20,
                height=10,
            )
            components.append(comp)

        generator = SchematicOverlayGenerator()

        img_path = _Path(f"data/schematics/{project_id}.png")
        if not img_path.exists():
            img_path = _Path(f"data/schematics/{project_id}.jpg")

        svg = generator.generate_overlay(
            image_path=str(img_path) if img_path.exists() else "tools/input.jpg",
            components=components,
            image_width=800,
            image_height=600,
        )

        return _Response(svg, mimetype="image/svg+xml")
    except PathSecurityError:
        return jsonify({"error": "Invalid file path"}), 400
    except Exception as e:
        logger.error("Schematic overlay error: %s", e)
        return jsonify({"error": "Failed to generate overlay"}), 500
