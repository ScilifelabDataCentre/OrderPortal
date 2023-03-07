"Command line interface to the OrderPortal database."

import json
import os.path
import time

import click
import couchdb2

from orderportal import constants, settings
from orderportal import utils
import orderportal.account
import orderportal.admin
import orderportal.config
import orderportal.database


@click.group()
def cli():
    "Command line interface for operations on the OrderPortal database."
    orderportal.config.load_settings_from_file()


@cli.command()
def destroy_database():
    "Hard delete of the entire database, including the instance within CouchDB."
    server = orderportal.database.get_server()
    try:
        db = server[settings["DATABASE_NAME"]]
    except couchdb2.NotFoundError as error:
        raise click.ClickException(str(error))
    db.destroy()
    click.echo(f"""Destroyed database '{settings["DATABASE_NAME"]}'.""")


@cli.command()
def create_database():
    "Create the database instance within CouchDB. Load the design document."
    server = orderportal.database.get_server()
    if settings["DATABASE_NAME"] in server:
        raise click.ClickException(
            f"""Database '{settings["DATABASE_NAME"]}' already exists."""
        )
    server.create(settings["DATABASE_NAME"])
    orderportal.database.update_design_documents(orderportal.database.get_db())
    click.echo(f"""Created database '{settings["DATABASE_NAME"]}'.""")


@cli.command()
def initialize():
    """Initialize database; load design documents.
    No longer needed. Kept just for backwards compatibility.
    """
    orderportal.database.update_design_documents(orderportal.database.get_db())


@cli.command()
@click.option("-v", "--verbose", count=True)
def counts(verbose):
    "Output counts of database entities."
    db = orderportal.database.get_db()
    orderportal.database.update_design_documents(db)
    click.echo(f"{orderportal.database.get_count(db, 'order', 'owner'):>5} orders")
    click.echo(f"{orderportal.database.get_count(db, 'form', 'all'):>5} forms")
    click.echo(f"{orderportal.database.get_count(db, 'account', 'all'):>5} accounts")
    click.echo(f"{orderportal.database.get_count(db, 'report', 'order'):>5} reports")

    count = 0
    for row in db.view("order", "obsolete_report", reduce=False, include_docs=True):
        if verbose:
            click.echo(f"{row.doc['identifier']} has an obsolete report.")
        count += 1
    click.echo(f"{count:>5} obsolete reports")


@cli.command()
@click.option(
    "-d", "--dumpfile", type=str, help="The path of the Orderportal database dump file."
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
    "Dump all data in the database to a '.tar.gz' dump file."
    db = orderportal.database.get_db()
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
    """Load an Orderportal database '.tar.gz' dump file.
    The database must exist and be empty.
    """
    try:
        db = orderportal.database.get_db()
    except KeyError as error:
        raise click.ClickException(str(error))
    orderportal.database.update_design_documents(db)
    if (
        orderportal.database.get_count(db, "account", "all") != 0
        or orderportal.database.get_count(db, "form", "all") != 0
        or orderportal.database.get_count(db, "order", "form") != 0
    ):
        raise click.ClickException(
            f"The database '{settings['DATABASE_NAME']}' contains data."
        )
    # Remove meta and text docs from the database since the dump
    # may contain updated versions of them.
    meta_docs = [row.doc for row in db.view("meta", "id", include_docs=True)]
    for doc in meta_docs:
        db.delete(doc)
        doc.pop("_rev")
    text_docs = [row.doc for row in db.view("text", "name", include_docs=True)]
    for doc in text_docs:
        db.delete(doc)
        doc.pop("_rev")
    ndocs, nfiles = db.undump(dumpfile, progressbar=progressbar)
    # NOTE: Meta documents must not have these id's; these are henceforth forbidden.
    for id in constants.FORBIDDEN_META_IDS:
        try:
            doc = db[id]
            db.delete(doc)
        except couchdb2.NotFoundError:
            pass
    # If lacking any meta or text doc, then add the initial one.
    for doc in meta_docs:
        if doc["_id"] not in db:
            db.put(doc)
    for doc in text_docs:
        if len(db.view("text", "name", key=doc["name"])) == 0:
            db.put(doc)
    # And finally update the formats of some meta documents.
    orderportal.admin.update_meta_documents(db)
    click.echo(f"Loaded {ndocs} documents and {nfiles} files.")


@cli.command()
@click.argument("email")
@click.option("--password")  # Get password after account existence check.
def create_admin(email, password):
    """Create a user account having the admin role.
    The email address is the account identifier.
    No email is sent to the email address by this command.
    """
    db = orderportal.database.get_db()
    try:
        with orderportal.account.AccountSaver(db=db) as saver:
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
    db = orderportal.database.get_db()
    try:
        account = _get_account(db, email)
    except KeyError as error:
        raise click.ClickException(str(error))
    try:
        with orderportal.account.AccountSaver(doc=account, db=db) as saver:
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
    db = orderportal.database.get_db()
    try:
        account = _get_account(db, email)
    except KeyError as error:
        raise click.ClickException(str(error))
    try:
        with orderportal.account.AccountSaver(doc=account, db=db) as saver:
            saver["role"] = role
    except ValueError as error:
        raise click.ClickException(str(error))
    click.echo(f"Role '{role}' set for account '{email}'.")


@cli.command()
@click.argument("identifier")
def output(identifier):
    """Output the JSON for the single document in the database.
    The identifier may be an account email, account API key, file name, info name,
    order identifier, or '_id' of the CouchDB document.
    """
    doc = orderportal.database.lookup_document(
        orderportal.database.get_db(), identifier
    )
    if doc is None:
        raise click.ClickException("No such item in the database.")
    click.echo(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
