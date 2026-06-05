This file conflicted with the installed 'prophet' package and was renamed.

To run the forecasting script use:

    python forecast.py

I moved the original `prophet.py` out of the import path to avoid shadowing the
installed `prophet` package. If you need the original source, see
`prophet_backup.py` in the same folder.
