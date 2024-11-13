import io
from datetime import datetime
from dateutil import parser

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    send_from_directory,
    redirect,
    url_for,
    flash,
    send_file,
)
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, StringField
import pandas as pd
import re
import os
import uuid
import tempfile

app = Flask(__name__)
app.secret_key = "your_secret_key_here"
app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp()
app.config["WTF_CSRF_ENABLED"] = False


class DataEntryForm(FlaskForm):
    values = FieldList(StringField())


def is_valid_regex(pattern):
    """Check if a string is a valid regex pattern."""
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


def is_regex_options_pattern(s):
    # Define a pattern to match a string that includes word characters, spaces, hyphens, and underscores
    pattern = re.compile(r"^\s*[\w\s\-_]+\s*(\|\s*[\w\s\-_]+\s*)*$")

    if pattern.fullmatch(s):
        categories = [option.strip() for option in s.split("|")]
        # print("Found categories: ", categories)
        return categories
    else:
        return []


def validate_field(value, rules, column_name: str = "", matched_column: bool = False):
    errors = []
    corrected_value = None
    column_name = column_name.strip()

    if rules["requiredness"] == "required" and (
        value is None or value == "" or value == "N/A"
    ):
        errors.append("This field is required")
    elif value and str(value) not in ["N/A", "n/a", "nan", ""]:
        if rules["class"] == "date":
            value = str(value).strip()
            desired_date_format = rules["allowedvalues"]

            # First check if only year with the following pattern is provided: '"2024' (check via regex), then just use the year as corrected value
            if re.match(r'^"\d{4}$', value):
                corrected_value = value[1:]
                return errors, corrected_value
            # or if just the year is provided, just take the year
            elif re.match(r"^´\d{4}$", value):
                corrected_value = value[1:]  # Remove the leading ´ character
                return errors, corrected_value

            # Check if the input pattern is `´MM.YYYY`, convert to the desired date format
            elif re.match(r"^´\d{2}\.\d{4}$", value):
                try:
                    # Extract month and year, parse it to a date object
                    month, year = value[1:].split(
                        "."
                    )  # Remove leading ´ and split by '.'
                    date_obj = datetime.strptime(f"{year}-{month}-01", "%Y-%m-%d")

                    # Check if the date format is a valid strftime format
                    try:
                        corrected_value = date_obj.strftime(desired_date_format)
                    except ValueError as e:
                        errors.append(
                            f"Invalid desired date format '{desired_date_format}': {e}"
                        )
                        return errors, value

                    # Debug: Print the corrected value
                    return errors, corrected_value

                except ValueError as e:
                    errors.append(f"Error parsing date: {e}")
                    return errors, value  # Return the original value if parsing fails

                # Or if just the year is provided, just take the year
            elif re.match(r"^\d{4}$", value):
                corrected_value = value
                return errors, corrected_value

            try:
                date_obj = parser.parse(value)

                # Format the datetime object to the desired format
                corrected_value = date_obj.strftime(desired_date_format)
            except ValueError:
                errors.append("Invalid date format")

            return errors, corrected_value

        if rules["class"] == "character" and not isinstance(value, str):
            if str(value) in ["nan", "NaN"]:
                if matched_column:
                    corrected_value = "N/A"
                else:
                    corrected_value = ""
                    errors.append("Missing Value")
            else:
                corrected_value = str(value)
                errors.append("Value should be a string")

        allowed_values = str(rules["allowedvalues"])

        # print("Validating value: ", value)

        if is_regex_options_pattern(allowed_values):
            allowed_values = is_regex_options_pattern(allowed_values)
            if str(value) not in allowed_values:
                print(
                    "Value not in allowed values, value: ",
                    value,
                    " column_name: ",
                    column_name,
                )
                if column_name and column_name.lower() in [
                    "gender",
                    "sex",
                    "geschlecht",
                ]:
                    print("Found sex column")
                    male_options = ["m", "männlich", "male", "man"]
                    female_options = ["w", "weiblich", "female", "f", "woman"]
                    diverse_options = ["d", "divers", "diverse"]

                    # Normalize the input value to lowercase
                    value_lower = str(value).lower().strip()

                    # Define a mapping for the possible corrections
                    corrections = {
                        "male": male_options,
                        "female": female_options,
                        "diverse": diverse_options,
                    }

                    # Try to correct the gender values automatically
                    for gender, options in corrections.items():
                        if value_lower in options:
                            corrected_value = gender
                            break

                for option in allowed_values:
                    if levenshtein_distance(str(value), option) <= 2:
                        corrected_value = option
                        break

                if not corrected_value:
                    errors.append(f"Value not in allowed values: {allowed_values}")

        elif is_valid_regex(allowed_values):
            print("Valid regex")
            if not re.match(allowed_values, str(value)):
                errors.append(f"Value does not match the pattern: {allowed_values}")

        elif allowed_values == "YYYYMMDD":
            if not re.match(r"^\d{4}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$", str(value)):
                errors.append("Value is not in YYYYMMDD format")
                # Try to correct the date format
                try:
                    date_obj = datetime.strptime(str(value), "%Y-%m-%d")
                    corrected_value = date_obj.strftime("%Y%m%d")
                except ValueError:
                    pass
        else:
            allowed_list = allowed_values.split("|")
            if str(value) not in allowed_list:
                errors.append(f"Value not in allowed values: {allowed_list}")
                # Try to find the closest match
                closest_match = min(
                    allowed_list, key=lambda x: levenshtein_distance(str(value), x)
                )
                if (
                    levenshtein_distance(str(value), closest_match) <= 2
                ):  # Adjust threshold as needed
                    corrected_value = closest_match

    else:
        print("Correcting value to N/A")
        if matched_column:
            corrected_value = "N/A"
        else:
            corrected_value = ""
            if rules["requiredness"] == "required":
                errors.append("Missing Value")
            # errors.append("Missing Value")

    return errors, corrected_value


def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def load_grammar(file):
    print("Grammar file: ", file)
    if file.filename.endswith(".xlsx"):
        grammar_df = pd.read_excel(file)
    elif file.filename.endswith(".csv"):
        grammar_df = pd.read_csv(file, delimiter=",")
    else:
        raise ValueError("Unsupported file format")
    grammar = {}
    for _, row in grammar_df.iterrows():
        if not str(row["col.name"]):
            print("Skipping empty grammar row")
            continue
        grammar[row["col.name"]] = {
            "class": row["col.class"],
            "uniqueness": row["uniqueness"],
            "requiredness": row["requiredness"],
            "multiplevalues": row["multiplevalues"],
            "allowedvalues": row["allowedvalues"],
        }
    return grammar


def normalize_column_name(name):
    return re.sub(r"[_\s]", "", str(name).lower())


def match_columns(grammar, data_columns):
    matched = {}
    unmatched = []
    data_columns_normalized = {normalize_column_name(col): col for col in data_columns}

    for gram_col in grammar:
        gram_col_normalized = normalize_column_name(gram_col)
        if gram_col_normalized in data_columns_normalized:
            matched[gram_col] = data_columns_normalized[gram_col_normalized]
        else:
            unmatched.append(gram_col)

    return matched, unmatched


@app.route("/validate", methods=["GET", "POST"])
def validate():
    if (
        "grammar" not in session
        or "data_filename" not in session
        or "matched" not in session
    ):
        return redirect(url_for("index"))

    grammar = session.get("grammar")
    filename = session.get("data_filename")
    matched = session.get("matched")

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if filename.endswith(".xlsx"):
        data = pd.read_excel(filepath)
    elif filename.endswith(".csv"):
        data = pd.read_csv(filepath)

    form = DataEntryForm()

    # Maintain the order of columns as specified in the grammar
    grammar_columns = list(grammar.keys())
    unmapped_columns = [col for col in data.columns if col not in matched.values()]
    all_columns = grammar_columns + unmapped_columns

    if request.method == "POST":
        updated_data = []
        errors = []
        corrected_values = []
        has_errors = False

        for i in range(0, len(form.values.data), len(all_columns)):
            row = {}
            row_errors = []
            row_corrected = []

            for j, col in enumerate(all_columns):
                value = form.values[i + j].data
                if col in grammar:
                    error, corrected = validate_field(
                        value,
                        grammar[col],
                        column_name=col,
                        matched_column=col in matched,
                    )
                    row[col] = corrected if corrected is not None else value
                    row_errors.append(", ".join(error) if error else "")
                    row_corrected.append(corrected)
                    if error:
                        has_errors = True
                else:
                    row[col] = value
                    row_errors.append("")
                    row_corrected.append(None)

            updated_data.append(row)
            errors.extend(row_errors)
            corrected_values.extend(row_corrected)

        if has_errors:
            # Populate form with corrected values
            for i, corrected in enumerate(corrected_values):
                if corrected is not None:
                    form.values[i].data = corrected
            num_errors = len([error for error in errors if error])
            return render_template(
                "validate.html",
                form=form,
                columns=all_columns,
                grammar_columns=grammar_columns,
                errors=errors,
                corrected_values=corrected_values,
                num_errors=num_errors,
            )
        elif "download" in request.form:
            # Save updated data
            # .to_csv(filepath, index=False)

            buffer = io.BytesIO()

            # Save the DataFrame to the buffer as a CSV
            pd.DataFrame(updated_data).to_csv(buffer, index=False)

            # Move the cursor to the start of the stream
            buffer.seek(0)

            # Send the file back to the user
            return send_file(
                buffer,
                as_attachment=True,
                download_name="data.csv",
                mimetype="text/csv",
            )

        else:
            num_errors = len([error for error in errors if error])
            return render_template(
                "validate.html",
                form=form,
                columns=all_columns,
                grammar_columns=grammar_columns,
                errors=errors,
                corrected_values=corrected_values,
                num_errors=num_errors,
            )

    else:  # GET request
        if not form.values.data:
            # Initial load
            errors = []
            corrected_values = []
            for _, row in data.iterrows():
                for col in all_columns:
                    if col in grammar:
                        value = row.get(matched.get(col), "")
                        error, corrected = validate_field(
                            value,
                            grammar[col],
                            column_name=col,
                            matched_column=col in matched,
                        )
                        form.values.append_entry(
                            corrected if corrected is not None else value
                        )
                        errors.append(", ".join(error) if error else "")
                        corrected_values.append(corrected)
                    else:
                        form.values.append_entry(row[col])
                        errors.append("")
                        corrected_values.append(None)

        num_errors = len([error for error in errors if error])

        return render_template(
            "validate.html",
            form=form,
            columns=all_columns,
            grammar_columns=grammar_columns,
            errors=errors,
            corrected_values=corrected_values,
            num_errors=num_errors,
        )


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "grammar" in request.files and "data" in request.files:
            grammar_file = request.files["grammar"]
            data_file = request.files["data"]

            grammar = load_grammar(grammar_file)
            if data_file.filename.endswith(".xlsx"):
                data = pd.read_excel(data_file)
            elif data_file.filename.endswith(".csv"):
                data = pd.read_csv(data_file)
            else:
                raise ValueError("Unsupported file format")

            # Save data file
            filename = secure_filename(f"{uuid.uuid4()}.csv")
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            data.to_csv(filepath, index=False)

            matched, unmatched = match_columns(grammar, data.columns)

            session["grammar"] = grammar
            session["data_filename"] = filename
            session["matched"] = matched
            session["unmatched"] = unmatched

            return render_template(
                "map_columns.html",
                grammar=grammar,
                data_columns=data.columns,
                matched=matched,
            )

    return render_template("index.html")


@app.route("/map_columns", methods=["POST"])
def map_columns():
    if "grammar" not in session or "data_filename" not in session:
        return redirect(url_for("index"))

    column_mapping = request.form.to_dict()
    grammar = session.get("grammar")
    matched = session.get("matched", {})

    for gram_col, data_col in column_mapping.items():
        if data_col != "None":
            matched[gram_col] = data_col

    session["matched"] = matched

    return redirect(url_for("validate"))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
