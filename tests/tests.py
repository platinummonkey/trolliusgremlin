"""
"""

import asyncio
import unittest
import uuid

from aiogremlin import (submit, GremlinConnector, GremlinClient,
                        GremlinClientSession)


class SubmitTest(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    def test_submit(self):

        @asyncio.coroutine
        def go():
            resp = yield from submit("4 + 4", bindings={"x": 4},
                                     loop=self.loop)
            results = yield from resp.get()
            return results

        results = self.loop.run_until_complete(go())
        self.assertEqual(results[0].data[0], 8)

    def test_rebinding(self):
        execute = submit("graph2.addVertex()", loop=self.loop)
        try:
            self.loop.run_until_complete(execute.get())
            error = False
        except:
            error = True
        self.assertTrue(error)

        @asyncio.coroutine
        def go():
            result = yield from submit(
                "graph2.addVertex()", rebindings={"graph2": "graph"},
                loop=self.loop)
            resp = yield from result.get()
            self.assertEqual(len(resp), 1)

        self.loop.run_until_complete(go())


class GremlinClientTest(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.gc = GremlinClient(url="ws://localhost:8182/", loop=self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.gc.close())
        self.loop.close()

    def test_connection(self):

        @asyncio.coroutine
        def go():
            ws = yield from self.gc._connector.ws_connect(self.gc.url)
            self.assertFalse(ws.closed)
            yield from ws.close()

        self.loop.run_until_complete(go())

    def test_execute(self):

        @asyncio.coroutine
        def go():
            resp = yield from self.gc.execute("x + x", bindings={"x": 4})
            return resp

        results = self.loop.run_until_complete(go())
        self.assertEqual(results[0].data[0], 8)

    def test_sub_waitfor(self):
        sub1 = self.gc.execute("x + x", bindings={"x": 1})
        sub2 = self.gc.execute("x + x", bindings={"x": 2})
        sub3 = self.gc.execute("x + x", bindings={"x": 4})
        coro = asyncio.gather(*[asyncio.async(sub1, loop=self.loop),
                              asyncio.async(sub2, loop=self.loop),
                              asyncio.async(sub3, loop=self.loop)],
                              loop=self.loop)
        # Here I am looking for resource warnings.
        results = self.loop.run_until_complete(coro)
        self.assertIsNotNone(results)

    def test_resp_stream(self):
        @asyncio.coroutine
        def stream_coro():
            results = []
            resp = yield from self.gc.submit("x + x", bindings={"x": 4})
            while True:
                f = yield from resp.stream.read()
                if f is None:
                    break
                results.append(f)
            self.assertEqual(results[0].data[0], 8)
        self.loop.run_until_complete(stream_coro())

    def test_execute_error(self):
        execute = self.gc.execute("x + x g.asdfas", bindings={"x": 4})
        try:
            self.loop.run_until_complete(execute)
            error = False
        except:
            error = True
        self.assertTrue(error)

    def test_rebinding(self):
        execute = self.gc.execute("graph2.addVertex()")
        try:
            self.loop.run_until_complete(execute)
            error = False
        except:
            error = True
        self.assertTrue(error)

        @asyncio.coroutine
        def go():
            result = yield from self.gc.execute(
                "graph2.addVertex()", rebindings={"graph2": "graph"})
            self.assertEqual(len(result), 1)

        self.loop.run_until_complete(go())



class GremlinClientSessionTest(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.gc = GremlinClientSession(url="ws://localhost:8182/",
                                       loop=self.loop)
        self.script1 = """graph = TinkerFactory.createModern()
                          g = graph.traversal(standard())"""

        self.script2 = "g.V().has('name','marko').out('knows').values('name')"

    def tearDown(self):
        self.loop.run_until_complete(self.gc.close())
        self.loop.close()

    def test_session(self):

        @asyncio.coroutine
        def go():
            yield from self.gc.execute(self.script1)
            results = yield from self.gc.execute(self.script2)
            return results

        results = self.loop.run_until_complete(go())
        self.assertTrue(len(results[0].data), 2)

    def test_session_reset(self):

        @asyncio.coroutine
        def go():
            yield from self.gc.execute(self.script1)
            self.gc.reset_session()
            results = yield from self.gc.execute(self.script2)
            return results

        results = self.loop.run_until_complete(go())
        self.assertIsNone(results[0].data)

    def test_session_manual_reset(self):

        @asyncio.coroutine
        def go():
            yield from self.gc.execute(self.script1)
            new_sess = str(uuid.uuid4())
            sess = self.gc.reset_session(session=new_sess)
            self.assertEqual(sess, new_sess)
            self.assertEqual(self.gc.session, new_sess)
            results = yield from self.gc.execute(self.script2)
            return results

        results = self.loop.run_until_complete(go())
        self.assertIsNone(results[0].data)

    def test_session_set(self):

        @asyncio.coroutine
        def go():
            yield from self.gc.execute(self.script1)
            new_sess = str(uuid.uuid4())
            self.gc.session = new_sess
            self.assertEqual(self.gc.session, new_sess)
            results = yield from self.gc.execute(self.script2)
            return results

        results = self.loop.run_until_complete(go())
        self.assertIsNone(results[0].data)

    def test_resp_session(self):

        @asyncio.coroutine
        def go():
            session = str(uuid.uuid4())
            self.gc.session = session
            resp = yield from self.gc.submit("x + x", bindings={"x": 4})
            while True:
                f = yield from resp.stream.read()
                if f is None:
                    break
            self.assertEqual(resp.session, session)

        self.loop.run_until_complete(go())


class ContextMngrTest(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.connector = GremlinConnector(loop=self.loop)

    def tearDown(self):
        self.loop.run_until_complete(self.connector.close())
        self.loop.close()

    # def test_connection_manager(self):
    #     results = []
    #
    #     @asyncio.coroutine
    #     def go():
    #         with (yield from self.connector) as conn:
    #             client = SimpleGremlinClient(conn, loop=self.loop)
    #             resp = yield from client.submit("1 + 1")
    #             while True:
    #                 mssg = yield from resp.stream.read()
    #                 if mssg is None:
    #                     break
    #                 results.append(mssg)
    #     self.loop.run_until_complete(go())


if __name__ == "__main__":
    unittest.main()
