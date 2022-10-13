"Command line interface to the OrderPortal database."

import json
import os.path
import time

import click
import couchdb2
import yaml

from orderportal import constants
from orderportal import designs
from orderportal import settings
from orderportal import utils
from orderportal.account import AccountSaver
from orderportal.admin import TextSaver
import orderportal.app_orderportal


@click.group()
@click.option("-s", "--settings", help="Path of settings YAML file.")
@click.option("--log", flag_value=True, default=False, help="Enable logging output.")
def cli(settings, log):
    utils.load_settings(settings, log=log)


@cli.command()
def destroy_database():
    "Hard delete of the entire database, including the instance within CouchDB."
    server = utils.get_dbserver()
    try:
        db = server[settings["DATABASE_NAME"]]
    except couchdb2.NotFoundError as error:
        raise click.ClickException(str(error))
    db.destroy()
    click.echo(f"""Destroyed database '{settings["DATABASE_NAME"]}'.""")


@cli.command()
def create_database():
    "Create the database within CouchDB. It is *not* initialized!"
    server = utils.get_dbserver()
    if settings["DATABASE_NAME"] in server:
        raise click.ClickException(f"""Database '{settings["DATABASE_NAME"]}' already exists.""")
    server.create(settings["DATABASE_NAME"])
    click.echo(f"""Created database '{settings["DATABASE_NAME"]}'.""")


@cli.command()
@click.option(
    "--textfile",
    type=str,
    default="../site/init_texts.yaml",
    help="The path of the initial texts YAML file.",
)
def initialize(textfile):
    """Initialize the database, which must exist and be empty.

    Load all design documents.
    Load the initial texts from the given file, if any.
    """
    try:
        db = utils.get_db()
    except KeyError as error:
        raise click.ClickException(str(error))
    if len(db) != 0:
        raise click.ClickException(
            f"The database '{settings['DATABASE_NAME']}' is not empty."
        )
    # Read the text file, if any. Check for errors before loading designs.
    if textfile:
        try:
            with open(textfile) as infile:
                texts = yaml.safe_load(infile)
        except IOError:
            raise click.ClickException(f"Could not read '{textfile}'.")
    else:
        texts = None
    designs.load_design_documents(db)
    click.echo("Loaded all design documents.")
    # Actually load the texts.
    if texts:
        for name in constants.TEXTS:
            if len(list(db.view("text", "name", key=name))) == 0:
                with TextSaver(db=db) as saver:
                    saver["name"] = name
                    saver["text"] = texts.get(name, "")
        click.echo(f"Loaded texts from '{textfile}'.")


@cli.command()
def counts():
    "Output counts of database entities."
    db = utils.get_db()
    designs.load_design_documents(db)
    click.echo(f"{utils.get_count(db, 'order', 'owner'):>5} orders")
    click.echo(f"{utils.get_count(db, 'form', 'all'):>5} forms")
    click.echo(f"{utils.get_count(db, 'account', 'all'):>5} accounts")


@cli.command()
@click.option(
    "-d",
    "--dumpfile",
    type=str,
    help="The path of the Orderportal database dump file."
    " NOTE: Environment variable BACKUP_DIR is no longer used.",
)
@click.option(
    "-D",
    "--dumpdir",
    type=str,
    help="The directory to write the dump file in, using the standard name.",
)
@click.option(
    "--progressbar/--no-progressbar", default=True, help="Display a progressbar."
)
def dump(dumpfile, dumpdir, progressbar):
    """Dump all data in the database to a .tar.gz dump file.
    NOTE: Environment variable BACKUP_DIR is no longer used.
    """
    db = utils.get_db()
    if not dumpfile:
        dumpfile = "dump_{0}.tar.gz".format(time.strftime("%Y-%m-%d"))
        if dumpdir:
            dumpfile = os.path.join(dumpdir, dumpfile)
    ndocs, nfiles = db.dump(dumpfile, exclude_designs=True, progressbar=progressbar)
    click.echo(f"Dumped {ndocs} documents and {nfiles} files to '{dumpfile}'.")


@cli.command()
@click.argument("dumpfile", type=click.Path(exists=True))
@click.option(
    "--progressbar/--no-progressbar", default=True, help="Display a progressbar."
)
def undump(dumpfile, progressbar):
    "Load a Orderportal database .tar.gz dump file. The database must exist and be empty."
    try:
        db = utils.get_db()
    except KeyError as error:
        raise click.ClickException(str(error))
    designs.load_design_documents(db)
    if (
        utils.get_count(db, "account", "all") != 0
        or utils.get_count(db, "form", "all") != 0
        or utils.get_count(db, "order", "form") != 0
    ):
        raise click.ClickException(
            f"The database '{settings['DATABASE_NAME']}' contains data."
        )
    ndocs, nfiles = db.undump(dumpfile, progressbar=progressbar)
    # Cleanup.
    # Remove old, obsolete meta documents.
    for name in ["account_messages", "order_messages"]:
        doc = db.get(name)
        if doc:
            db.delete(doc)
    # Text docs are doubled; youngest copy is from initialize.
    # Keep only oldest version (from dump) of text docs.
    lookup = {}
    for row in db.view("text", "name", include_docs=True):
        if not row.doc["name"] in lookup:
            lookup[row.doc["name"]] = row.doc
        elif lookup[row.doc["name"]]["modified"] <= row.doc["modified"]:
            db.delete(row.doc)
        else:
            db.delete(lookup.pop(row.doc["name"]))
            lookup[row.doc["name"]] = row.doc
    click.echo(f"Loaded {ndocs} documents and {nfiles} files.")


@cli.command()
@click.option("--email", prompt=True, help="Email address = account name")
@click.option("--password")  # Get password after account existence check.
def create_admin(email, password):
    "Create a user account having the admin role."
    db = utils.get_db()
    try:
        with AccountSaver(db=db) as saver:
            saver.set_email(email)
            if not password:
                password = click.prompt(
                    "Password", hide_input=True, confirmation_prompt=True
                )
            saver.set_password(password)
            saver["first_name"] = click.prompt("First name")
            saver["last_name"] = click.prompt("Last name")
            saver["address"] = dict()
            saver["invoice_address"] = dict()
            saver["university"] = click.prompt("University")
            saver["department"] = None
            saver["owner"] = email
            saver["role"] = constants.ADMIN
            saver["status"] = constants.ENABLED
            saver["api_key"] = utils.get_iuid()
            saver["labels"] = []
    except ValueError as error:
        raise click.ClickException(str(error))
    click.echo(f"Created 'admin' role account '{email}'.")


@cli.command()
@click.option("--email", prompt=True)
@click.option("--password")  # Get password after account existence check.
def password(email, password):
    "Set the password for the given account."
    db = utils.get_db()
    try:
        account = _get_account(db, email)
    except KeyError as error:
        raise click.ClickException(str(error))
    try:
        with AccountSaver(doc=account, db=db) as saver:
            if not password:
                password = click.prompt(
                    "Password", hide_input=True, confirmation_prompt=True
                )
            saver.set_password(password)
            saver["status"] = constants.ENABLED
    except ValueError as error:
        raise click.ClickException(str(error))
    click.echo(f"Password set for account '{email}'.")


def _get_account(db, email):
    "Get the account for the given email."
    view = db.view(
        "account", "email", key=email.lower(), reduce=False, include_docs=True
    )
    result = list(view)
    if len(result) == 1:
        return result[0].doc
    else:
        raise KeyError(f"No such account '{email}'.")


@cli.command()
@click.option("--email", prompt=True)
@click.option(
    "--role",
    type=click.Choice(constants.ACCOUNT_ROLES, case_sensitive=False),
    default=constants.USER,
)
def role(email, role):
    "Set the role for the given account."
    db = utils.get_db()
    try:
        account = _get_account(db, email)
    except KeyError as error:
        raise click.ClickException(str(error))
    try:
        with AccountSaver(doc=account, db=db) as saver:
            saver["role"] = role
    except ValueError as error:
        raise click.ClickException(str(error))
    click.echo(f"Role '{role}' set for account '{email}'.")


@cli.command()
@click.argument("identifier")
def show(identifier):
    """Display the JSON for the single item in the database.
    The identifier may be an email, API key, file name, info name,
    order identifier, or IUID of the document.
    """
    db = utils.get_db()
    for designname, viewname in [
        ("account", "email"),
        ("account", "api_key"),
        ("file", "name"),
        ("info", "name"),
        ("order", "identifier"),
    ]:
        try:
            view = db.view(
                designname, viewname, key=identifier, reduce=False, include_docs=True
            )
            result = list(view)
            if len(result) == 1:
                doc = result[0].doc
                break
        except KeyError:
            pass
    else:
        try:
            doc = db[identifier]
        except couchdb2.NotFoundError:
            raise click.ClickException("No such item in the database.")
    click.echo(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
