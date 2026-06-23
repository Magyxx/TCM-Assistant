# Device2 vLLM Serving Report

Stage: `D2-T2: vLLM Repair and Serving Integration`

Generated at: `2026-06-23T03:30:44+00:00`

Status: `serving_deferred`

## Environment Isolation

* training env: `/home/magyxx/venvs/tcm-device2-train-py312-cu126-final`
* serving env: `/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124`
* training env was not modified by vLLM installation or serving probes

## Version Matrix

```json
{
  "command_result": {
    "command": [
      "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/bin/python",
      "-c",
      "\nimport importlib\nimport json\npayload = {\"imports\": {}}\nfor name in [\"torch\", \"vllm\", \"openai\"]:\n    try:\n        mod = importlib.import_module(name)\n        payload[\"imports\"][name] = {\"ok\": True, \"version\": getattr(mod, \"__version__\", \"unknown\")}\n    except Exception as exc:\n        payload[\"imports\"][name] = {\"ok\": False, \"error\": f\"{type(exc).__name__}: {exc}\"}\ntry:\n    import torch\n    payload[\"torch\"] = {\n        \"version\": torch.__version__,\n        \"cuda_version\": torch.version.cuda,\n        \"cuda_available\": torch.cuda.is_available(),\n        \"device_count\": torch.cuda.device_count(),\n        \"device_name\": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,\n    }\nexcept Exception as exc:\n    payload[\"torch\"] = {\"error\": f\"{type(exc).__name__}: {exc}\"}\nprint(json.dumps(payload, ensure_ascii=False))\n"
    ],
    "returncode": 0,
    "stdout_tail": "{\"imports\": {\"torch\": {\"ok\": true, \"version\": \"2.5.1+cu124\"}, \"vllm\": {\"ok\": true, \"version\": \"0.6.6.post1\"}, \"openai\": {\"ok\": true, \"version\": \"2.43.0\"}}, \"torch\": {\"version\": \"2.5.1+cu124\", \"cuda_version\": \"12.4\", \"cuda_available\": true, \"device_count\": 1, \"device_name\": \"NVIDIA GeForce RTX 4070\"}}\n",
    "stderr_tail": "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/transformers/utils/hub.py:128: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.\n  warnings.warn(\n",
    "elapsed_seconds": 4.618
  },
  "ok": true,
  "imports": {
    "torch": {
      "ok": true,
      "version": "2.5.1+cu124"
    },
    "vllm": {
      "ok": true,
      "version": "0.6.6.post1"
    },
    "openai": {
      "ok": true,
      "version": "2.43.0"
    }
  },
  "torch": {
    "version": "2.5.1+cu124",
    "cuda_version": "12.4",
    "cuda_available": true,
    "device_count": 1,
    "device_name": "NVIDIA GeForce RTX 4070"
  }
}
```

## Serving Smoke

* `/v1/models`: `False`
* `/v1/chat/completions` base: `False`
* `/v1/chat/completions` LoRA: `False`

## Failure Classification

* `WSL runtime issue`

## Server Log Tail

```text
/lib/python3.12/site-packages/vllm/engine/llm_engine.py", line 276, in __init__
    self._initialize_kv_caches()
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/engine/llm_engine.py", line 416, in _initialize_kv_caches
    self.model_executor.determine_num_available_blocks())
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/executor/gpu_executor.py", line 68, in determine_num_available_blocks
    return self.driver_worker.determine_num_available_blocks()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/torch/utils/_contextlib.py", line 116, in decorate_context
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/worker/worker.py", line 202, in determine_num_available_blocks
    self.model_runner.profile_run()
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/torch/utils/_contextlib.py", line 116, in decorate_context
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/worker/model_runner.py", line 1331, in profile_run
    self.execute_model(model_input, kv_caches, intermediate_tensors)
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/torch/utils/_contextlib.py", line 116, in decorate_context
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/worker/model_runner_base.py", line 152, in _wrapper
    raise type(err)(
RuntimeError: Error in model execution (input dumped to /tmp/err_execute_model_input_20260623-113032.pkl): Failed to find C compiler. Please specify via CC environment variable.
[rank0]:[W623 11:30:33.881116652 ProcessGroupNCCL.cpp:1250] Warning: WARNING: process group has NOT been destroyed before we destruct ProcessGroupNCCL. On normal program exit, the application should call destroy_process_group to ensure that any pending NCCL operations have finished in this process. In rare cases this process can exit before this point and block the progress of another member of the process group. This constraint has always been present,  but this warning has only been added since PyTorch 2.4 (function operator())
Task exception was never retrieved
future: <Task finished name='Task-2' coro=<MQLLMEngineClient.run_output_handler_loop() done, defined at /home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/engine/multiprocessing/client.py:178> exception=ZMQError('Operation not supported')>
Traceback (most recent call last):
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/engine/multiprocessing/client.py", line 184, in run_output_handler_loop
    while await self.output_socket.poll(timeout=VLLM_RPC_TIMEOUT
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/zmq/_future.py", line 386, in poll
    raise _zmq.ZMQError(_zmq.ENOTSUP)
zmq.error.ZMQError: Operation not supported
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 774, in <module>
    uvloop.run(run_server(args))
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/uvloop/__init__.py", line 96, in run
    return __asyncio.run(
           ^^^^^^^^^^^^^^
  File "/home/magyxx/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/asyncio/runners.py", line 195, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/home/magyxx/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/uvloop/__init__.py", line 48, in wrapper
    return await main
           ^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 740, in run_server
    async with build_async_engine_client(args) as engine_client:
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 118, in build_async_engine_client
    async with build_async_engine_client_from_engine_args(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/magyxx/venvs/tcm-device2-serving-py312-vllm-d2t2-cu124/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 223, in build_async_engine_client_from_engine_args
    raise RuntimeError(
RuntimeError: Engine process failed to start. See stack trace for the root cause.

```
