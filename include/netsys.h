#ifndef NETSYS_H
#define NETSYS_H

#include <stddef.h>
#include <stdint.h>

#ifndef ENABLE_DEBUG
#define ENABLE_DEBUG 0
#endif

#define NET_MAX_FRAME 4096U
#define NET_DEFAULT_PORT 9090

void net_set_log(const char *role, int debug_enabled);
void net_log(const char *level, const char *format, ...)
    __attribute__((format(printf, 2, 3)));
int net_debug_enabled(void);
#if ENABLE_DEBUG
#define NET_DEBUG(...) do { if (net_debug_enabled()) net_log("DEBUG", __VA_ARGS__); } while (0)
#else
#define NET_DEBUG(...) do { } while (0)
#endif

int64_t net_now_ms(void);
int net_parse_long(const char *text, long minimum, long maximum, long *value);
int net_nonblocking(int fd);
int net_connect(const char *host, int port, int timeout_ms);
int net_listen(const char *host, int port, int backlog);
/* Return 1 for a frame, 0 for clean EOF, -1 with errno on failure. */
int net_recv_frame(int fd, char *buffer, size_t capacity, int timeout_ms, int robust);
int net_send_frame(int fd, const char *payload, int timeout_ms);

#endif
