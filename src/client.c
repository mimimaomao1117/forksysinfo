#define _POSIX_C_SOURCE 200809L
#include "netsys.h"

#include <errno.h>
#include <getopt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void usage(FILE *stream, const char *program) {
    fprintf(stream, "Usage: %s [--host IPv4] [--port N] [--timeout-ms N] [--debug] COMMAND [ARG ...]\n"
                    "Commands: SYSINFO | PING | ECHO text | SLEEP milliseconds | QUIT\n", program);
}

int main(int argc, char **argv) {
    const char *host = "127.0.0.1";
    int port = NET_DEFAULT_PORT, timeout = 5000, debug = 0;
    static const struct option options[] = {
        {"host", required_argument, NULL, 'H'}, {"port", required_argument, NULL, 'p'},
        {"timeout-ms", required_argument, NULL, 't'}, {"debug", no_argument, NULL, 'd'},
        {"help", no_argument, NULL, 'h'}, {NULL, 0, NULL, 0}
    };
    int option;
    long value;
    while ((option = getopt_long(argc, argv, "+H:p:t:dh", options, NULL)) != -1) {
        switch (option) {
        case 'H': host = optarg; break;
        case 'p': if (net_parse_long(optarg, 1, 65535, &value) < 0) goto invalid; port = (int)value; break;
        case 't': if (net_parse_long(optarg, 1, 600000, &value) < 0) goto invalid; timeout = (int)value; break;
        case 'd': debug = 1; break;
        case 'h': usage(stdout, argv[0]); return 0;
        default: goto invalid;
        }
    }
    if (optind >= argc) goto invalid;
    net_set_log("client", debug);
    signal(SIGPIPE, SIG_IGN);
    char request[NET_MAX_FRAME + 1] = "";
    size_t used = 0;
    for (int index = optind; index < argc; ++index) {
        size_t length = strlen(argv[index]);
        size_t separator = index == optind ? 0 : 1;
        if (used + separator + length > NET_MAX_FRAME) {
            net_log("ERROR", "REQUEST_TOO_LARGE max=%u", NET_MAX_FRAME);
            return 2;
        }
        if (separator) request[used++] = ' ';
        memcpy(request + used, argv[index], length);
        used += length;
        request[used] = '\0';
    }
    NET_DEBUG("CONNECT host=%s port=%d timeout_ms=%d", host, port, timeout);
    int fd = net_connect(host, port, timeout);
    if (fd < 0) { net_log("ERROR", "CONNECT_FAILED errno=%d %s", errno, strerror(errno)); return 1; }
    if (net_send_frame(fd, request, timeout) < 0) {
        net_log("ERROR", "SEND_FAILED errno=%d %s", errno, strerror(errno)); close(fd); return 1;
    }
    char response[NET_MAX_FRAME + 1];
    int result = net_recv_frame(fd, response, sizeof(response), timeout, 1);
    if (result <= 0) {
        if (result == 0) net_log("ERROR", "SERVER_CLOSED_WITHOUT_RESPONSE");
        else net_log("ERROR", "RECEIVE_FAILED errno=%d %s", errno, strerror(errno));
        close(fd);
        return 1;
    }
    puts(response);
    close(fd);
    return strncmp(response, "OK", 2) == 0 ? 0 : 1;
invalid:
    usage(stderr, argv[0]);
    return 2;
}
