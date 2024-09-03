# GraDaCu - **Gra**mmar-based **Da**ta **Cu**ration

Curate your tabular data using grammar rules. 

## Usage

Create a Python environment and install the dependencies using the following commands:

`pip install -r requirements.txt`

To run the code, use the following command:

`python app.py`

Now you can open your browser and go to `http://localhost:5000/` to use the application.
Adjust the Host and Port in the `app.py` file if needed.

## Grammar File

The grammar file is a CSV / XLSX file that contains the following columns:

| col.name | col.class | uniqueness | requiredness | multiplevalues | allowedvalues                   |
|---------|-----------|------------|--------------|----------------|---------------------------------|
| Name    | character | non-unique | required     | FALSE          | (?:[a-z]      \|[A-Z])[a-zA-Z]+ |
| ID      | character | unique     | required     | FALSE          | (?:[a-z]      \|[A-Z])[a-zA-Z]+ |
| Date    | date      | non-unique | optional     | FALSE          | %m/%Y                           |
| Type    | character | non-unique | optional     | TRUE           | categoryA\|categoryB\|categoryC |

Your data can be in CSV / XLSX format. It should contain the columns specified in the grammar. The application will validate the data based on the grammar rules.