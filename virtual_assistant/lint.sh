#!/bin/bash

# Navigate to your project's root directory if the script is not there
# cd /path/to/your/project

black .

# Run flake8 on your project
flake8 .
