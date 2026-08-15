from registry import main

if __name__ == "__main__":
    raise SystemExit(main(["list", *__import__("sys").argv[1:]]))
