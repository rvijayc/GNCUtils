# GNC Utilities

A project to streamline transaction entry into GNUCash. 

## Installation

This project uses GNUCash Python Bindings which require you to compile them (via SWIG) for the specific Python version that you plan to use. Here are the instructions to do so:

Create a conda environment with a specific Python version and requirements pre-installed.

```shell
conda env create -f environment.yaml
```

Checkout my forked version of GNUCash that has additional build scripts.

```shell
git clone git@github.com:rvijayc/gnucash.git
```

Build GNUCash with Python bindings enabled.


