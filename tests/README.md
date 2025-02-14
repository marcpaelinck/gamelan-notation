In Visual Studio Code, add the following to settings.json:
```
    "python.testing.pytestArgs": [
        "--cache-clear",
        "-s"
    ],

```
The -s is optional, it will cause the tested function's output to be sent tot the Test Result output channel.