from registry import main

if __name__ == "__main__":
    raise SystemExit(main(["lookup", *__import__("sys").argv[1:]]))
