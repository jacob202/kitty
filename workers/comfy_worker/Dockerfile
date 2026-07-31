# Supply the exact image backing the private RunPod ComfyUI template.
# Example: docker build --build-arg COMFYUI_BASE_IMAGE=<verified-image-ref> ...
ARG COMFYUI_BASE_IMAGE
FROM ${COMFYUI_BASE_IMAGE}

USER root
WORKDIR /opt/kitty

COPY workers/comfy_worker/requirements.txt /tmp/kitty-worker-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/kitty-worker-requirements.txt

COPY workers /opt/kitty/workers
COPY workflows /opt/kitty/workflows
COPY workers/comfy_worker/start.sh /opt/kitty/start-kitty-worker.sh
RUN chmod 0555 /opt/kitty/start-kitty-worker.sh

ENV PYTHONPATH=/opt/kitty \
    COMFY_URL=http://127.0.0.1:8188 \
    KITTY_WORKFLOW_ROOT=/opt/kitty/workflows \
    KITTY_JOB_ROOT=/workspace/jobs

EXPOSE 8000
CMD ["/opt/kitty/start-kitty-worker.sh"]
