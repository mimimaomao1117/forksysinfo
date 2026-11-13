#define _POSIX_C_SOURCE 200809L
#include "netsys.h"

#include <arpa/inet.h>
#include <errno.h>
#include <getopt.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/sysinfo.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define CHILD_LIMIT 1024
static volatile sig_atomic_t stopping;
static void stop_handler(int number) { (void)number; stopping = 1; }
static void child_handler(int number) { (void)number; }

static int set_handler(int number, void (*handler)(int)) {
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = handler;
    sigemptyset(&action.sa_mask);
    return sigaction(number, &action, NULL);
}

static void usage(FILE *stream, const char *program) {
    fprintf(stream, "Usage: %s [--host IPv4] [--port N] [--timeout-ms N] [--max-clients N] [--debug] [--unsafe]\n"
                    "--unsafe is a teaching mode: single recv, no idle deadline, no child reaping.\n", program);
}

static void system_info(char *response, size_t size) {
    struct utsname name;
    struct sysinfo info;
    char hostname[256];
    if (uname(&name) < 0 || sysinfo(&info) < 0 || gethostname(hostname, sizeof(hostname)) < 0) {
        snprintf(response, size, "ERR SYSINFO %s", strerror(errno));
        return;
    }
    hostname[sizeof(hostname) - 1] = '\0';
    snprintf(response, size,
             "OK SYSINFO\nhostname=%s\nsysname=%s\nrelease=%s\nmachine=%s\npid=%ld\n"
             "uptime_seconds=%ld\nram_total_bytes=%llu\nram_free_bytes=%llu",
             hostname, name.sysname, name.release, name.machine, (long)getpid(),
             info.uptime, (unsigned long long)info.totalram * info.mem_unit,
             (unsigned long long)info.freeram * info.mem_unit);
}

static int handle_command(const char *request, char *response, size_t size) {
    if (strcmp(request, "PING") == 0) {
        snprintf(response, size, "OK PONG pid=%ld", (long)getpid());
    } else if (strcmp(request, "SYSINFO") == 0) {
        system_info(response, size);
    } else if (strncmp(request, "ECHO ", 5) == 0) {
        if (strlen(request + 5) > NET_MAX_FRAME - 3) snprintf(response, size, "ERR ECHO_TOO_LONG");
        else snprintf(response, size, "OK %s", request + 5);
    } else if (strncmp(request, "SLEEP ", 6) == 0) {
        long milliseconds;
        if (net_parse_long(request + 6, 0, 10000, &milliseconds) < 0) {
            snprintf(response, size, "ERR BAD_ARGUMENT SLEEP accepts 0..10000 milliseconds");
        } else {
            struct timespec delay = { .tv_sec = milliseconds / 1000, .tv_nsec = (milliseconds % 1000) * 1000000L };
            while (nanosleep(&delay, &delay) < 0 && errno == EINTR) { }
            snprintf(response, size, "OK SLEPT %ld pid=%ld", milliseconds, (long)getpid());
        }
    } else if (strcmp(request, "QUIT") == 0) {
        snprintf(response, size, "OK BYE");
        return 1;
    } else {
        snprintf(response, size, "ERR UNKNOWN_COMMAND");
    }
    return 0;
}

static void serve_client(int fd, int timeout, int robust, int debug) {
    net_set_log("worker", debug);
    char request[NET_MAX_FRAME + 1], response[NET_MAX_FRAME + 1];
    for (;;) {
        int result = net_recv_frame(fd, request, sizeof(request), robust ? timeout : -1, robust);
        if (result == 0) { NET_DEBUG("PEER_EOF"); break; }
        if (result < 0) {
            int saved = errno;
            net_log("WARN", "FRAME_READ_ERROR errno=%d %s", saved, strerror(saved));
            const char *error = saved == ETIMEDOUT ? "ERR TIMEOUT" :
                                saved == EMSGSIZE ? "ERR BAD_LENGTH" : "ERR BAD_FRAME";
            (void)net_send_frame(fd, error, 300);
            break;
        }
        NET_DEBUG("COMMAND bytes=%zu", strlen(request));
        int quit = handle_command(request, response, sizeof(response));
        if (net_send_frame(fd, response, timeout) < 0) {
            net_log("WARN", "FRAME_WRITE_ERROR errno=%d %s", errno, strerror(errno));
            break;
        }
        if (quit) break;
    }
    close(fd);
    net_log("INFO", "CHILD_DONE");
}

static void remove_child(pid_t *children, size_t *count, pid_t pid) {
    for (size_t index = 0; index < *count; ++index) {
        if (children[index] == pid) {
            children[index] = children[--(*count)];
            return;
        }
    }
}

static void reap_children(pid_t *children, size_t *count) {
    int status;
    pid_t pid;
    while ((pid = waitpid(-1, &status, WNOHANG)) > 0) {
        remove_child(children, count, pid);
        net_log("INFO", "REAP child=%ld active=%zu status=%d", (long)pid, *count, status);
    }
}

int main(int argc, char **argv) {
    const char *host = "127.0.0.1";
    int port = NET_DEFAULT_PORT, timeout = 2000, max_clients = 64, debug = 0, robust = 1;
    static const struct option options[] = {
        {"host", required_argument, NULL, 'H'}, {"port", required_argument, NULL, 'p'},
        {"timeout-ms", required_argument, NULL, 't'}, {"max-clients", required_argument, NULL, 'm'},
        {"debug", no_argument, NULL, 'd'}, {"unsafe", no_argument, NULL, 'u'},
        {"help", no_argument, NULL, 'h'}, {NULL, 0, NULL, 0}
    };
    int option;
    long value;
    while ((option = getopt_long(argc, argv, "H:p:t:m:duh", options, NULL)) != -1) {
        switch (option) {
        case 'H': host = optarg; break;
        case 'p': if (net_parse_long(optarg, 1, 65535, &value) < 0) goto invalid; port = (int)value; break;
        case 't': if (net_parse_long(optarg, 1, 600000, &value) < 0) goto invalid; timeout = (int)value; break;
        case 'm': if (net_parse_long(optarg, 1, CHILD_LIMIT, &value) < 0) goto invalid; max_clients = (int)value; break;
        case 'd': debug = 1; break;
        case 'u': robust = 0; break;
        case 'h': usage(stdout, argv[0]); return 0;
        default: goto invalid;
        }
    }
    if (optind != argc) goto invalid;
    net_set_log("server", debug);
    if (set_handler(SIGTERM, stop_handler) < 0 || set_handler(SIGINT, stop_handler) < 0 ||
        set_handler(SIGCHLD, child_handler) < 0 || set_handler(SIGPIPE, SIG_IGN) < 0) {
        net_log("ERROR", "SIGNAL_SETUP_FAILED %s", strerror(errno)); return 1;
    }
    int listener = net_listen(host, port, 128);
    if (listener < 0) { net_log("ERROR", "LISTEN_FAILED errno=%d %s", errno, strerror(errno)); return 1; }
    pid_t children[CHILD_LIMIT];
    size_t count = 0;
    net_log("INFO", "READY host=%s port=%d robust=%d timeout_ms=%d max_clients=%d compiled_debug=%d",
            host, port, robust, timeout, max_clients, ENABLE_DEBUG);
    if (!robust) net_log("WARN", "UNSAFE_TEACHING_MODE partial_read_recovery=off idle_deadline=off child_reaping=off");
    NET_DEBUG("DEBUG_BUILD runtime_debug=on");
    while (!stopping) {
        if (robust) reap_children(children, &count);
        struct pollfd item = { .fd = listener, .events = POLLIN, .revents = 0 };
        int ready = poll(&item, 1, 100);
        if (ready < 0) {
            if (errno == EINTR) continue;
            net_log("ERROR", "POLL_FAILED %s", strerror(errno));
            break;
        }
        if (ready == 0) continue;
        struct sockaddr_in peer;
        socklen_t peer_size = sizeof(peer);
        int fd = accept(listener, (struct sockaddr *)&peer, &peer_size);
        if (fd < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK || errno == ECONNABORTED) continue;
            net_log("WARN", "ACCEPT_FAILED errno=%d %s", errno, strerror(errno));
            struct timespec pause = { .tv_sec = 0, .tv_nsec = 100000000L };
            nanosleep(&pause, NULL);
            continue;
        }
        if (net_nonblocking(fd) < 0) { close(fd); continue; }
        if (robust) reap_children(children, &count);
        if (count >= (size_t)max_clients) {
            net_log("WARN", "CLIENT_LIMIT active=%zu max=%d", count, max_clients);
            (void)net_send_frame(fd, "ERR SERVER_BUSY", 100);
            close(fd);
            continue;
        }
        /* A worker must install default termination handlers before an early
           parent shutdown can send SIGTERM. Otherwise it could inherit the
           parent's flag-only handler and keep serving while waitpid blocks. */
        sigset_t termination_signals, old_mask;
        sigemptyset(&termination_signals);
        sigaddset(&termination_signals, SIGINT);
        sigaddset(&termination_signals, SIGTERM);
        if (sigprocmask(SIG_BLOCK, &termination_signals, &old_mask) < 0) {
            net_log("ERROR", "SIGNAL_MASK_FAILED %s", strerror(errno));
            close(fd);
            continue;
        }
        pid_t child = fork();
        if (child < 0) {
            int saved = errno;
            (void)sigprocmask(SIG_SETMASK, &old_mask, NULL);
            errno = saved;
            net_log("ERROR", "FORK_FAILED errno=%d %s", errno, strerror(errno));
            (void)net_send_frame(fd, "ERR SERVER_BUSY", 100);
            close(fd);
            continue;
        }
        if (child == 0) {
            close(listener);
            set_handler(SIGTERM, SIG_DFL);
            set_handler(SIGINT, SIG_DFL);
            set_handler(SIGCHLD, SIG_DFL);
            (void)sigprocmask(SIG_SETMASK, &old_mask, NULL);
            serve_client(fd, timeout, robust, debug);
            _exit(0);
        }
        close(fd);
        children[count++] = child;
        (void)sigprocmask(SIG_SETMASK, &old_mask, NULL);
        char peer_text[INET_ADDRSTRLEN] = "?";
        inet_ntop(AF_INET, &peer.sin_addr, peer_text, sizeof(peer_text));
        net_log("INFO", "FORK child=%ld active=%zu peer=%s:%u", (long)child, count,
                peer_text, (unsigned)ntohs(peer.sin_port));
    }
    close(listener);
    /* Shutdown deliberately reaps in both modes so the comparison leaves no debris. */
    for (size_t index = 0; index < count; ++index) (void)kill(children[index], SIGTERM);
    while (count > 0) {
        int status;
        pid_t child = waitpid(-1, &status, 0);
        if (child > 0) remove_child(children, &count, child);
        else if (errno != EINTR) break;
    }
    net_log("INFO", "STOPPED active=%zu", count);
    return 0;
invalid:
    usage(stderr, argv[0]);
    return 2;
}
