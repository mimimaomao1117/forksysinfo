CC ?= gcc
DEBUG ?= 1
ifeq ($(DEBUG),1)
MODE := debug
OPT := -O0 -g3
else ifeq ($(DEBUG),0)
MODE := release
OPT := -O2
else
$(error DEBUG must be 0 or 1)
endif

BUILD := build/$(MODE)
CPPFLAGS += -Iinclude -DENABLE_DEBUG=$(DEBUG)
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic -Werror $(OPT)
LDFLAGS +=

.PHONY: all clean test debug release
all: $(BUILD)/server $(BUILD)/client

$(BUILD):
	mkdir -p $@

$(BUILD)/netsys.o: src/netsys.c include/netsys.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -c $< -o $@

$(BUILD)/libnetsys.so: $(BUILD)/netsys.o
	$(CC) -shared $(LDFLAGS) -Wl,-soname,libnetsys.so $< -o $@

$(BUILD)/server: src/server.c include/netsys.h $(BUILD)/libnetsys.so
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -L$(BUILD) -lnetsys -Wl,-rpath,'$$ORIGIN' $(LDFLAGS) -o $@

$(BUILD)/client: src/client.c include/netsys.h $(BUILD)/libnetsys.so
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -L$(BUILD) -lnetsys -Wl,-rpath,'$$ORIGIN' $(LDFLAGS) -o $@

debug:
	$(MAKE) DEBUG=1 all

release:
	$(MAKE) DEBUG=0 all

test: all
	python3 tests/run_tests.py

clean:
	rm -rf build
