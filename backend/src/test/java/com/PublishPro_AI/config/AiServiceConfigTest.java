package com.PublishPro_AI.config;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

/*
 * Real sockets, no mocks: a tiny local server records what the AI service client
 * actually puts on the wire.
 *
 * Why this matters: Java's HTTP client asks plain-http servers to "upgrade" to HTTP/2
 * by default. uvicorn (the Python server) does not support that. It loses the request
 * body (FastAPI then answers 422 "body: Field required"), answers 400 "Invalid HTTP
 * request received", or resets the connection (which Spring reports as "not reachable").
 */
class AiServiceConfigTest {

    private record Received(Headers headers, String body) {
    }

    private static HttpServer startServer(List<Received> received) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        server.createContext("/echo", exchange -> {
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            received.add(new Received(exchange.getRequestHeaders(), body));

            byte[] answer = "{}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, answer.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(answer);
            }
        });
        server.start();
        return server;
    }

    @Test
    void theClientSendsPlainHttp11AndNeverAsksForAnUpgrade() throws Exception {
        List<Received> received = new ArrayList<>();
        HttpServer server = startServer(received);
        try {
            AiServiceProperties properties = new AiServiceProperties(
                    "http://127.0.0.1:" + server.getAddress().getPort(),
                    "secret",
                    Duration.ofSeconds(5)
            );
            RestClient client = new AiServiceConfig().aiServiceClient(properties);

            // Several calls with one client, the way the running backend uses it.
            for (int call = 1; call <= 3; call++) {
                client.post()
                        .uri("/echo")
                        .body(Map.of("video_topic", "A topic that is long enough"))
                        .retrieve()
                        .toBodilessEntity();
            }

            assertEquals(3, received.size());
            for (Received request : received) {
                assertNull(request.headers().getFirst("Upgrade"));
                assertNull(request.headers().getFirst("HTTP2-Settings"));
                String connection = request.headers().getFirst("Connection");
                assertFalse(connection != null && connection.toLowerCase().contains("upgrade"));
                // The body is there, in full.
                assertEquals("{\"video_topic\":\"A topic that is long enough\"}", request.body());
            }
        } finally {
            server.stop(0);
        }
    }

    @Test
    void theClientUsesTheConfiguredBaseUrl() throws Exception {
        List<Received> received = new ArrayList<>();
        HttpServer server = startServer(received);
        try {
            AiServiceProperties properties = new AiServiceProperties(
                    "http://127.0.0.1:" + server.getAddress().getPort(),
                    "secret",
                    Duration.ofSeconds(5)
            );

            new AiServiceConfig().aiServiceClient(properties)
                    .post().uri("/echo").body(Map.of("a", "b")).retrieve().toBodilessEntity();

            assertEquals(1, received.size());
        } finally {
            server.stop(0);
        }
    }
}
