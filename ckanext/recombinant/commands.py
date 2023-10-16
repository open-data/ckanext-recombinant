from ckan.lib.cli import CkanCommand


class TableCommand(CkanCommand):
    summary = "\nDEPRECATED: use `ckan [-c/--c=<config>] recombinant` instead.\n"
    usage = "\nDEPRECATED: use `ckan [-c/--c=<config>] recombinant` instead.\n"

    def command(self):
        """
        \nDEPRECATED: use `ckan [-c/--c=<config>] recombinant` instead.\n
        """
        return
