# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/tonyp7/ifrit/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                        |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|-------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| app/api/auth.py                             |       61 |        5 |       10 |        2 |     90% |97, 101-102, 124-\>128, 126-127 |
| app/api/companies.py                        |      136 |        7 |       26 |        4 |     93% |172, 177-179, 197, 241, 269 |
| app/api/files.py                            |       33 |        5 |       10 |        1 |     86% |41-43, 45-46 |
| app/api/invoice\_template.py                |      105 |        8 |       10 |        1 |     92% |54, 63-64, 99-100, 140-142 |
| app/api/invoices.py                         |      164 |       10 |       12 |        1 |     94% |183-185, 284-285, 319-320, 349, 363, 403 |
| app/api/projects.py                         |      232 |        6 |       14 |        1 |     97% |62, 182-183, 240, 338-339 |
| app/api/users.py                            |       66 |        5 |        6 |        0 |     93% |80, 101, 126-128 |
| app/auth/dependencies.py                    |       28 |        2 |        6 |        0 |     94% |     26-27 |
| app/auth/security.py                        |       36 |        0 |        4 |        1 |     98% |   46-\>48 |
| app/core/body\_limit.py                     |       33 |        4 |       12 |        2 |     87% |31-32, 40-41, 54-\>65 |
| app/core/db.py                              |       11 |        2 |        0 |        0 |     82% |     17-18 |
| app/pdf/odt.py                              |      212 |       16 |       88 |        9 |     90% |60-\>58, 64-65, 139, 161-162, 173-175, 211, 214, 256-\>exit, 274-277, 288, 314 |
| app/pdf/runner.py                           |      114 |       15 |       16 |        2 |     87% |76-\>78, 85-87, 159-161, 197-207, 209-210 |
| app/pdf/validate.py                         |      176 |        4 |       86 |        1 |     98% |84-85, 102-103, 248-\>244 |
| app/schemas/company.py                      |      112 |        8 |       36 |        8 |     89% |29, 53, 86, 117, 119, 162, 164, 195 |
| app/schemas/invoice.py                      |      152 |        1 |       42 |        1 |     99% |       157 |
| app/schemas/project.py                      |       68 |        3 |       24 |        3 |     93% |89, 91, 139 |
| app/schemas/user.py                         |       51 |        5 |       22 |        5 |     86% |50, 52, 83, 85, 87 |
| app/services/app\_settings.py               |       52 |        1 |        8 |        1 |     97% |        54 |
| app/services/company\_service.py            |      134 |        2 |       24 |        1 |     98% |     62-63 |
| app/services/file\_storage\_service.py      |      289 |       17 |       44 |        4 |     92% |325, 331, 333-334, 511-513, 544-\>exit, 593-599, 635-638 |
| app/services/invoice\_numbering\_service.py |       84 |        0 |       22 |        1 |     99% | 59-\>exit |
| app/services/invoice\_service.py            |      469 |       13 |      144 |       15 |     95% |317, 452, 616, 730, 759, 786, 853, 919-\>927, 922, 1130, 1286, 1320-\>1322, 1336, 1353-1354, 1381-\>1383 |
| app/services/project\_service.py            |      290 |        5 |       76 |        5 |     97% |279, 329, 359, 408, 433 |
| app/services/report\_export\_service.py     |      388 |        4 |       98 |        7 |     98% |84-\>87, 102-\>100, 104, 126-\>123, 128, 862, 876 |
| app/services/time\_entry\_service.py        |      179 |        4 |       60 |        6 |     96% |240-\>243, 469, 508-\>521, 583, 624, 681 |
| app/services/user\_service.py               |      104 |        1 |       20 |        1 |     98% |       107 |
| **TOTAL**                                   | **5141** |  **153** | **1050** |   **83** | **96%** |           |

53 files skipped due to complete coverage.


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/tonyp7/ifrit/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/tonyp7/ifrit/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/tonyp7/ifrit/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/tonyp7/ifrit/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Ftonyp7%2Fifrit%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/tonyp7/ifrit/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.