#define _POSIX_C_SOURCE 200809L
#include "netsys.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static const char *log_role = "unknown";
static int runtime_debug;

void net_set_log(const char *role, int debug_enabled) {
    log_role = role;
    runtime_debug = debug_enabled;
}

int net_debug_enabled(void) { return runtime_debug; }

void net_log(const char *level, const char *format, ...) {
    char line[2048];
    struct timespec now;
    struct tm stamp;
    char time_text[32];
    clock_gettime(CLOCK_REALTIME, &now);
    localtime_r(&now.tv_sec, &stamp);
    strftime(time_text, sizeof(time_text), "%Y-%m-%dT%H:%M:%S", &stamp);
    int used = snprintf(line, sizeof(line), "%s.%03ld %s pid=%ld role=%s ",
                        time_text, now.tv_nsec / 1000000L, level, (long)getpid(), log_role);
    if (used < 0 || (size_t)used >= sizeof(line)) return;
    va_list args;
    va_start(args, format);
    int extra = vsnprintf(line + used, sizeof(line) - (size_t)used, format, args);
    va_end(args);
    if (extra < 0) return;
    size_t size = (size_t)used + (size_t)extra;
    if (size > sizeof(line) - 2) size = sizeof(line) - 2;
    line[size++] = '\n';
    /* One short write keeps individual process log records together. */
    ssize_t ignored = write(STDERR_FILENO, line, size);
    (void)ignored;
}

int64_t net_now_ms(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) return -1;
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

int net_parse_long(const char *text, long minimum, long maximum, long *value) {
    char *end;
    if (!text || !*text) return -1;
    errno = 0;
    long result = strtol(text, &end, 10);
    if (errno || *end || result < minimum || result > maximum) return -1;
    *value = result;
    return 0;
}

int net_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    return flags < 0 ? -1 : fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static int wait_ready(int fd, short events, int64_t deadline) {
    for (;;) {
        int timeout = -1;
        if (deadline >= 0) {
            int64_t remaining = deadline - net_now_ms();
            if (remaining <= 0) { errno = ETIMEDOUT; return -1; }
            timeout = remaining > INT_MAX ? INT_MAX : (int)remaining;
        }
        struct pollfd item = { .fd = fd, .events = events, .revents = 0 };
        int result = poll(&item, 1, timeout);
        if (result > 0) {
            if (item.revents & POLLNVAL) { errno = EBADF; return -1; }
            /* recv/send reports the precise error for HUP and ERR. */
            return 0;
        }
        if (result == 0) { errno = ETIMEDOUT; return -1; }
        if (errno != EINTR) return -1;
    }
}

static int read_bytes(int fd, void *buffer, size_t length, int64_t deadline,
                      int robust, int allow_clean_eof) {
    size_t received = 0;
    while (received < length) {
        if (wait_ready(fd, POLLIN, deadline) < 0) return -1;
        ssize_t count = recv(fd, (char *)buffer + received, length - received, 0);
        if (count == 0) {
            if (received == 0 && allow_clean_eof) return 0;
            errno = ECONNRESET;
            return -1;
        }
        if (count < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) continue;
            return -1;
        }
        received += (size_t)count;
        if (!robust && received < length) { errno = EPROTO; return -1; }
    }
    return 1;
}

int net_recv_frame(int fd, char *buffer, size_t capacity, int timeout_ms, int robust) {
    uint32_t wire_length;
    int64_t deadline = timeout_ms < 0 ? -1 : net_now_ms() + timeout_ms;
    int result = read_bytes(fd, &wire_length, sizeof(wire_length), deadline, robust, 1);
    if (result <= 0) return result;
    uint32_t length = ntohl(wire_length);
    if (length == 0 || length > NET_MAX_FRAME || (size_t)length >= capacity) {
        errno = EMSGSIZE;
        return -1;
    }
    result = read_bytes(fd, buffer, length, deadline, robust, 0);
    if (result < 0) return -1;
    if (memchr(buffer, '\0', length)) { errno = EPROTO; return -1; }
    buffer[length] = '\0';
    NET_DEBUG("FRAME_RX bytes=%u", length);
    return 1;
}

int net_send_frame(int fd, const char *payload, int timeout_ms) {
    size_t length = strlen(payload);
    if (length == 0 || length > NET_MAX_FRAME) { errno = EMSGSIZE; return -1; }
    unsigned char frame[NET_MAX_FRAME + 4];
    uint32_t wire_length = htonl((uint32_t)length);
    memcpy(frame, &wire_length, 4);
    memcpy(frame + 4, payload, length);
    size_t sent = 0;
    int64_t deadline = timeout_ms < 0 ? -1 : net_now_ms() + timeout_ms;
    while (sent < length + 4) {
        if (wait_ready(fd, POLLOUT, deadline) < 0) return -1;
        ssize_t count = send(fd, frame + sent, length + 4 - sent, MSG_NOSIGNAL);
        if (count < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) continue;
            return -1;
        }
        if (count == 0) { errno = EPIPE; return -1; }
        sent += (size_t)count;
    }
    NET_DEBUG("FRAME_TX bytes=%zu", length);
    return 0;
}

static int make_address(const char *host, int port, struct sockaddr_in *address) {
    memset(address, 0, sizeof(*address));
    address->sin_family = AF_INET;
    address->sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, host, &address->sin_addr) != 1) { errno = EINVAL; return -1; }
    return 0;
}

int net_connect(const char *host, int port, int timeout_ms) {
    struct sockaddr_in address;
    if (make_address(host, port, &address) < 0) return -1;
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    if (net_nonblocking(fd) < 0) goto failure;
    if (connect(fd, (struct sockaddr *)&address, sizeof(address)) == 0) return fd;
    if (errno != EINPROGRESS) goto failure;
    if (wait_ready(fd, POLLOUT, net_now_ms() + timeout_ms) < 0) goto failure;
    int socket_error = 0;
    socklen_t size = sizeof(socket_error);
    if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &socket_error, &size) < 0) goto failure;
    if (socket_error) { errno = socket_error; goto failure; }
    return fd;
failure: {
        int saved = errno;
        close(fd);
        errno = saved;
        return -1;
    }
}

int net_listen(const char *host, int port, int backlog) {
    struct sockaddr_in address;
    if (make_address(host, port, &address) < 0) return -1;
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    int enabled = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled)) < 0 ||
        net_nonblocking(fd) < 0 ||
        bind(fd, (struct sockaddr *)&address, sizeof(address)) < 0 ||
        listen(fd, backlog) < 0) {
        int saved = errno;
        close(fd);
        errno = saved;
        return -1;
    }
    return fd;
}
