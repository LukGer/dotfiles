#!/usr/bin/env python3
import json
import subprocess
import sys


def main():
    command = ["claude", "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", *sys.argv[1:]]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as process:
        for line in process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                print(line, end="", flush=True)
                continue
            if message.get("type") == "stream_event":
                delta = message["event"].get("delta", {})
                if delta.get("type") == "text_delta":
                    print(delta["text"], end="", flush=True)
            elif message.get("type") == "assistant":
                for block in message["message"]["content"]:
                    if block["type"] == "tool_use":
                        arguments = block.get("input", {})
                        detail = next((arguments[key] for key in ("description", "file_path", "command", "pattern")
                                       if arguments.get(key)), "")
                        print(f"\n{block['name']}: {detail}", flush=True)
            elif message.get("type") == "result" and message.get("is_error"):
                error = message.get("result") or "\n".join(message.get("errors", []))
                print(error, file=sys.stderr, flush=True)
        print(flush=True)
        return process.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
