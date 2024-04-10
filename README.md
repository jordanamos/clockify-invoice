# Clockify Invoice

Creates invoices using clockify's API. Option to run a local server so invoices can be generated/managed in a browser. Can be run in a docker container.

## Requires weasyprint
-  Windows See https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows

## Installation
```
pip install clockify-invoice
```

## Setup
1. Set CLOCKIFY_INVOICE_HOME environment variable to define where your invoices and config will be stored. If not set a sensible directoy within your home directory will be used (usually ~/clockify-invoice/):
    ```
    export CLOCKIFY_INVOICE_HOME=/path/to/your/home
    ```
2. Run clockify-invoice command to generate the necessary config file within the directory specified above.
    ```
    clockify-invoice
    ```
3. Edit the clockify-invoice-config.json file to include your API_KEY and other details. This tool also searches for your api key in the CLOCKIFY_API_KEY environment variable.

4. Synch the local database with clockify with --synch
    ```
    clockify-invoice --synch
    ```
5. Run an interactive session in the browser with -i
    ```
    clockify-invoice -i
    ```

## Docker

1. Clone this repository
    ```
    git clone git@github.com:jordanamos/clockify-invoice.git
    ```
2. Follow steps 1-3 in `Setup`
3. Edit docker-compose.yml to expose the same flask and mail ports in the config file (5000 and 465 by default). Also update docker-compose.yml volumes to mount your local CLOCKIFY_INVOICE_HOME directory with a /invoices folder within the container (this should be the same as the CLOCKIFY_INVOICE_HOME environment variable value that is defined in the Dockerfile)
4. Build and run the contianer
    ```
    docker-compose up --build
    ```
