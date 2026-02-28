{
    'name': "Database Connector",
    'version': '1.0',
    'depends': ['base'],
    'author': "Marcelo Santos",
    'company': "Corvanis",
    'category': "Tools",
    'license': 'LGPL-3',
    'description': """
This module provides a connector to external databases, allowing you to fetch and manipulate data from various sources directly within Odoo. It supports multiple database types, including MySQL, PostgreSQL, and SQL Server, enabling seamless integration with your existing data infrastructure.
    """,
    # data files always loaded at installation
    # 'data': [
    #     'views/mymodule_view.xml',
    # ],
    # data files containing optionally loaded demonstration data
    # 'demo': [
    #     'demo/demo_data.xml',
    # ],
    'installable': True,
    'auto_install': False,
    'application': True,
}