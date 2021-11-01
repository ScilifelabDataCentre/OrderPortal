"Command line interface to the OrderPortal database."

import io
import json
import os.path
import tarfile
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
@click.option("--log", flag_value=True, default=False,
              help="Enable logging output.")
def cli(settings, log):
    utils.load_settings(settings, log=log)

@cli.command()
@click.option("--textfile", type=str, default="../site/init_texts.yaml",
                help="The path of the initial texts YAML file.")
def initialize(textfile):
    """Initialize the database, which must exist and be empty.

    Load all design documents. Create the meta document. Load the
    initial texts from the given file, if any.
    """
    try:
        db = utils.get_db()
    except KeyError as error:
        raise click.ClickException(str(error))
    if len(db) != 0:
        raise click.ClickException(
            f"The database '{settings['DATABASE_NAME']}' is not empty.")
    # Read the text file, if any.
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
    # Create the meta document.
    # No specific items set here; done on-the-fly in e.g. get_next_number
    db.put(dict(_id='order', orderportal_doctype=constants.META))
    click.echo("Created the meta document.")
    # Actually load the texts.
    if texts:
        for name in constants.TEXTS:
            if len(list(db.view("text", "name", key=name))) == 0:
                with TextSaver(db=db) as saver:
                    saver['name'] = name
                    saver['text'] = texts.get(name, '')
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
@click.option("-d", "--dumpfile", type=str,
                help="The path of the Orderportal database dump file."
              " NOTE: Environment variable BACKUP_DIR is no longer used.")
@click.option("-D", "--dumpdir", type=str,
                help="The directory to write the dump file in, using the standard name.")
def dump(dumpfile, dumpdir):
    """Dump all data in the database to a .tar.gz dump file.
    NOTE: Environment variable BACKUP_DIR is no longer used.
    """
    db = utils.get_db()
    if not dumpfile:
        dumpfile = "dump_{0}.tar.gz".format(time.strftime("%Y-%m-%d"))
        if dumpdir:
            filepath = os.path.join(dumpdir, dumpfile)
    count_items = 0
    count_files = 0
    if dumpfile.endswith(".gz"):
        mode = "w:gz"
    else:
        mode = "w"
    with tarfile.open(dumpfile, mode=mode) as outfile:
        with click.progressbar(db, label="Dumping...") as bar:
            for doc in bar:
                # Only documents that explicitly belong to the application.
                if doc.get(constants.DOCTYPE) is None: continue
                rev = doc.pop("_rev")
                info = tarfile.TarInfo(doc["_id"])
                data = json.dumps(doc).encode("utf-8")
                info.size = len(data)
                outfile.addfile(info, io.BytesIO(data))
                count_items += 1
                doc["_rev"] = rev       # Revision required to get attachments.
                for attname in doc.get("_attachments", dict()):
                    info = tarfile.TarInfo(f"{doc['_id']}_att/{attname}")
                    attfile = db.get_attachment(doc, attname)
                    if attfile is None: continue
                    data = attfile.read()
                    attfile.close()
                    info.size = len(data)
                    outfile.addfile(info, io.BytesIO(data))
                    count_files += 1
    click.echo(f"Dumped {count_items} items and {count_files} files to {dumpfile}")

@cli.command()
@click.argument("dumpfile", type=click.Path(exists=True))
def undump(dumpfile):
    "Load a Orderportal database .tar.gz dump file. The database must be empty."
    db = utils.get_db()
    designs.load_design_documents(db)
    if (utils.get_count(db, "account", "all") != 0 or
        utils.get_count(db, "form", "all") != 0 or
        utils.get_count(db, "order", "form") != 0):
        raise click.ClickException(
            f"The database '{settings['DATABASE_NAME']}' contains data.")
    count_items = 0
    count_files = 0
    attachments = dict()
    try:
        with tarfile.open(dumpfile, mode="r") as infile:
            length = sum(1 for member in infile if member.isreg())
    except IOError as error:
        raise click.ClickException(str(error))
    with tarfile.open(dumpfile, mode="r") as infile:
        # First remove the meta document, if any, to avoid revision error.
        try:
            db.delete(db["order"])
        except couchdb2.NotFoundError:
            pass
        with click.progressbar(infile, label="Loading...", length=length) as bar:
            for item in bar:
                itemfile = infile.extractfile(item)
                itemdata = itemfile.read()
                itemfile.close()
                if item.name in attachments:
                    # This relies on an attachment being after its item in the tarfile.
                    db.put_attachment(doc, itemdata, **attachments.pop(item.name))
                    count_files += 1
                else:
                    doc = json.loads(itemdata)
                    atts = doc.pop("_attachments", dict())
                    db.put(doc)
                    count_items += 1
                    for attname, attinfo in list(atts.items()):
                        key = f"{doc['_id']}_att/{attname}"
                        attachments[key] = dict(filename=attname, 
                                                content_type=attinfo["content_type"])
    click.echo(f"Loaded {count_items} items and {count_files} files.")

@cli.command()
@click.option("--email", prompt=True, help="Email address = account name")
@click.option("--password")     # Get password after account existence check.
def admin(email, password):
    "Create a user account having the admin role."
    db = utils.get_db()
    try:
        with AccountSaver(db=db) as saver:
            saver.set_email(email)
            if not password:
                password = click.prompt("Password", 
                                        hide_input=True,
                                        confirmation_prompt=True)
            saver.set_password(password)
            saver["first_name"] = click.prompt("First name")
            saver["last_name"] = click.prompt("Last name")
            saver['address'] = dict()
            saver['invoice_address'] = dict()
            saver["university"] = click.prompt("University")
            saver['department'] = None
            saver['owner'] = email
            saver['role'] = constants.ADMIN
            saver['status'] = constants.ENABLED
            saver['labels'] = []
    except ValueError as error:
        raise click.ClickException(str(error))
    click.echo(f"Created 'admin' role account '{email}'.")

@cli.command()
@click.option("--email", prompt=True)
@click.option("--password")     # Get password after account existence check.
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
                password = click.prompt("Password", 
                                        hide_input=True,
                                        confirmation_prompt=True)
            saver.set_password(password)
    except ValueError as error:
        raise click.ClickException(str(error))
    click.echo(f"Password set for account '{email}'.")

def _get_account(db, email):
    "Get the account for the given email."
    view = db.view("account",
                   "email",
                   key=email.lower(),
                   reduce=False,
                   include_docs=True)
    result = list(view)
    if len(result) == 1:
        return result[0].doc
    else:
        raise KeyError(f"No such account '{email}'.")

@cli.command()
@click.option("--email", prompt=True)
@click.option("--role",
              type=click.Choice(constants.ACCOUNT_ROLES, case_sensitive=False),
              default=constants.USER)
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
    for designname, viewname in [("account", "email"),
                                 ("account", "api_key"),
                                 ("file", "name"),
                                 ("info", "name"),
                                 ("order", "identifier")]:
        try:
            view = db.view(designname,
                           viewname,
                           key=identifier,
                           reduce=False,
                           include_docs=True)
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
    click.echo(json_dumps(doc))

def json_dumps(doc): return json.dumps(doc, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    cli()
