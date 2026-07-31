# Supply the exact image backing the private RunPod ComfyUI template.
# The pinned reference lives in workers/comfy_worker/runpod-template-image.json
# and is consumed deterministically by the build workflow — never discovered
# from the RunPod API at build time.
# Example: docker build --build-arg COMFYUI_BASE_IMAGE=$(jq -r .image_name workers/comfy_worker/runpod-template-image.json) ...
ARG COMFYUI_BASE_IMAGE
FROM ${COMFYUI_BASE_IMAGE}

USER root
WORKDIR /opt/kitty

COPY workers/comfy_worker/requirements.txt /tmp/kitty-worker-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/kitty-worker-requirements.txt

COPY workers /opt/kitty/workers
COPY workflows /opt/kitty/workflows
COPY workers/comfy_worker/entrypoint-kitty.sh /opt/kitty/entrypoint-kitty.sh
COPY workers/comfy_worker/bootstrap.sh /opt/kitty/bootstrap.sh
RUN chmod 0555 /opt/kitty/entrypoint-kitty.sh /opt/kitty/bootstrap.sh

ENV PYTHONPATH=/opt/kitty \
    COMFY_URL=http://127.0.0.1:8188 \
    KITTY_WORKFLOW_ROOT=/opt/kitty/workflows \
    KITTY_JOB_ROOT=/workspace/jobs

EXPOSE 8000 8188
ENTRYPOINT ["/opt/kitty/entrypoint-kitty.sh"]
CMD ["/opt/kitty/bootstrap.sh"]
