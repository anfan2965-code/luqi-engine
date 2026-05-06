import pytest
from luqi_engine.core.middleware import MiddlewareBase, LoggingMiddleware, MiddlewarePipeline


class EchoMiddleware(MiddlewareBase):
    def __init__(self, tag: str = ""):
        self.tag = tag
        self.request_seen: list = []
        self.response_seen: list = []

    def process_request(self, request):
        self.request_seen.append(request)
        request["tags"] = request.get("tags", []) + [f"req_{self.tag}"]
        return request

    def process_response(self, response):
        self.response_seen.append(response)
        response["tags"] = response.get("tags", []) + [f"resp_{self.tag}"]
        return response


class ErrorMiddleware(MiddlewareBase):
    def process_request(self, request):
        raise RuntimeError("request boom")

    def process_response(self, response):
        raise RuntimeError("response boom")


class TestLoggingMiddleware:
    def test_process_request_passes_through(self):
        mw = LoggingMiddleware()
        req = {"action": "test"}
        result = mw.process_request(req)
        assert result is req

    def test_process_response_passes_through(self):
        mw = LoggingMiddleware()
        resp = {"status": "ok"}
        result = mw.process_response(resp)
        assert result is resp


class TestMiddlewarePipelineBasic:
    def setup_method(self):
        self.pipeline = MiddlewarePipeline()

    def test_empty_pipeline_count(self):
        assert self.pipeline.middleware_count == 0

    def test_add_middleware(self):
        self.pipeline.add_middleware(LoggingMiddleware())
        assert self.pipeline.middleware_count == 1

    def test_remove_middleware_by_type(self):
        self.pipeline.add_middleware(LoggingMiddleware())
        assert self.pipeline.remove_middleware(LoggingMiddleware)
        assert self.pipeline.middleware_count == 0

    def test_remove_nonexistent_returns_false(self):
        assert self.pipeline.remove_middleware(EchoMiddleware) is False

    def test_clear(self):
        self.pipeline.add_middleware(LoggingMiddleware())
        self.pipeline.add_middleware(LoggingMiddleware())
        self.pipeline.clear()
        assert self.pipeline.middleware_count == 0


class TestMiddlewarePipelineRequestOrder:
    def test_request_executes_in_addition_order(self):
        pipeline = MiddlewarePipeline()
        m1 = EchoMiddleware("a")
        m2 = EchoMiddleware("b")
        pipeline.add_middleware(m1)
        pipeline.add_middleware(m2)
        result = pipeline.process_request({"action": "go"})
        assert "req_a" in result["tags"]
        assert "req_b" in result["tags"]
        assert result["tags"].index("req_a") < result["tags"].index("req_b")

    def test_request_with_single_middleware(self):
        pipeline = MiddlewarePipeline()
        m = EchoMiddleware("solo")
        pipeline.add_middleware(m)
        result = pipeline.process_request({"action": "solo"})
        assert result["tags"] == ["req_solo"]


class TestMiddlewarePipelineResponseOrder:
    def test_response_executes_in_reverse_order(self):
        pipeline = MiddlewarePipeline()
        m1 = EchoMiddleware("x")
        m2 = EchoMiddleware("y")
        pipeline.add_middleware(m1)
        pipeline.add_middleware(m2)
        result = pipeline.process_response({"status": "ok"})
        assert "resp_x" in result["tags"]
        assert "resp_y" in result["tags"]
        assert result["tags"].index("resp_y") < result["tags"].index("resp_x")


class TestMiddlewarePipelineExecute:
    def test_full_pipeline_roundtrip(self):
        pipeline = MiddlewarePipeline()
        m1 = EchoMiddleware("1")
        m2 = EchoMiddleware("2")
        pipeline.add_middleware(m1)
        pipeline.add_middleware(m2)

        def handler(req):
            return {"result": req["action"], "status": "done", **req}

        response = pipeline.execute({"action": "compute"}, handler)
        assert response["result"] == "compute"
        assert response["status"] == "done"
        assert "resp_1" in response["tags"]
        assert "resp_2" in response["tags"]

    def test_handler_receives_processed_request(self):
        received = {}

        def capture(req):
            received.update(req)
            return {"ok": True}

        pipeline = MiddlewarePipeline()
        pipeline.add_middleware(EchoMiddleware("cap"))
        pipeline.execute({"data": 99}, capture)
        assert "req_cap" in received["tags"]
        assert received["data"] == 99


class TestMiddlewarePipelineErrorHandling:
    def test_request_error_does_not_stop_pipeline(self):
        pipeline = MiddlewarePipeline()
        pipeline.add_middleware(ErrorMiddleware())
        pipeline.add_middleware(EchoMiddleware("after"))
        result = pipeline.process_request({"action": "risky"})
        assert "req_after" in result["tags"]

    def test_response_error_does_not_stop_pipeline(self):
        pipeline = MiddlewarePipeline()
        pipeline.add_middleware(ErrorMiddleware())
        pipeline.add_middleware(EchoMiddleware("after"))
        result = pipeline.process_response({"status": "risky"})
        assert "resp_after" in result["tags"]
