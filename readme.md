# Furnace: XSLT-based site generator

```
Usage: furnace [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

  Static site generator using XSL templates.

Options:
  -L, --log-level [CRITICAL|ERROR|WARNING|INFO|DEBUG]
                                  Set logging level. Defaults to WARNING.
  -p, --project PATH              Choose the project configuration file.
                                  Defaults to ./furnace.project.yaml. Ignored
                                  if `furnace build` is called with a
                                  repository URL.
  -d, --data PATH                 Choose the data file furnace will create and
                                  use. Defaults to ./furnace-data.xml. Ignored
                                  if `furnace build` is called with a
                                  repository URL.
  --help                          Show this message and exit.

Commands:
  build        Build the entire site from scratch.
  collect      Collects all datasources.
  fetch        Fetches git repositories.
  generate     Generates pages from XSL templates.
  postprocess  Runs all postprocessing directives.
  preprocess   Runs all preprocessing directives.
  static       Copies static directories into output.
  update       `git pull` the project's repository.
```