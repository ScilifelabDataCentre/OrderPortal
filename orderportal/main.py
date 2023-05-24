"OrderPortal web application server."

import logging
import os.path

import tornado.web
import tornado.ioloop

from orderportal import constants, settings
from orderportal import utils

import orderportal.account
import orderportal.admin
import orderportal.config
import orderportal.database
import orderportal.file
import orderportal.form
import orderportal.group
import orderportal.info
import orderportal.home
import orderportal.order
import orderportal.report
import orderportal.search
import orderportal.uimodules


def get_handlers():
    url = tornado.web.url
    return [
        url(r"/", orderportal.home.Home, name="home"),
        url(r"/status", orderportal.home.Status, name="status"),
        url(r"/contact", orderportal.home.Contact, name="contact"),
        url(r"/about", orderportal.home.About, name="about"),
        url(r"/documentation", orderportal.home.Documentation, name="documentation"),
        url(r"/software", orderportal.home.Software, name="software"),
        url(r"/log/([0-9a-f]{32})", orderportal.home.Log, name="log"),
        url(r"/([0-9a-f]{32})", orderportal.home.Entity, name="entity"),
        url(r"/order", orderportal.order.OrderCreate, name="order_create"),
        url(
            r"/api/v1/order",
            orderportal.order.OrderCreateApiV1,
            name="order_create_api",
        ),
        url(r"/order/([^/.]+)", orderportal.order.Order, name="order"),
        url(r"/api/v1/order/([^/.]+)", orderportal.order.OrderApiV1, name="order_api"),
        url(r"/order/([^/]+).csv", orderportal.order.OrderCsv, name="order_csv"),
        url(r"/order/([^/]+).xlsx", orderportal.order.OrderXlsx, name="order_xlsx"),
        url(r"/order/([^/]+).zip", orderportal.order.OrderZip, name="order_zip"),
        url(
            r"/order/([0-9a-f]{32})/logs",
            orderportal.order.OrderLogs,
            name="order_logs",
        ),
        url(
            r"/order/([0-9a-f]{32})/edit",
            orderportal.order.OrderEdit,
            name="order_edit",
        ),
        url(
            r"/order/([0-9a-f]{32})/owner",
            orderportal.order.OrderOwner,
            name="order_owner",
        ),
        url(
            r"/order/([0-9a-f]{32})/clone",
            orderportal.order.OrderClone,
            name="order_clone",
        ),
        url(
            r"/order/([0-9a-f]{32})/transition/(\w+)",
            orderportal.order.OrderTransition,
            name="order_transition",
        ),
        url(
            r"/api/v1/order/([0-9a-f]{32})/transition/(\w+)",
            orderportal.order.OrderTransitionApiV1,
            name="order_transition_api",
        ),
        url(
            r"/order/([0-9a-f]{32})/file",
            orderportal.order.OrderFile,
            name="order_file_add",
        ),
        url(
            r"/order/([0-9a-f]{32})/file/([^/]+)",
            orderportal.order.OrderFile,
            name="order_file",
        ),
        url(r"/orders", orderportal.order.Orders, name="orders"),
        url(r"/api/v1/orders", orderportal.order.OrdersApiV1, name="orders_api"),
        url(r"/orders.csv", orderportal.order.OrdersCsv, name="orders_csv"),
        url(r"/orders.xlsx", orderportal.order.OrdersXlsx, name="orders_xlsx"),
        url(r"/report", orderportal.report.ReportAdd, name="report_add"),
        url(
            r"/api/v1/report", orderportal.report.ReportAddApiV1, name="report_add_api"
        ),
        url(r"/report/([0-9a-f]{32})", orderportal.report.Report, name="report"),
        url(
            r"/api/v1/report/([0-9a-f]{32})",
            orderportal.report.ReportApiV1,
            name="report_api",
        ),
        url(
            r"/report/([0-9a-f]{32})/edit",
            orderportal.report.ReportEdit,
            name="report_edit",
        ),
        url(
            r"/report/([0-9a-f]{32})/review",
            orderportal.report.ReportReview,
            name="report_review",
        ),
        url(
            r"/report/([0-9a-f]{32})/logs",
            orderportal.report.ReportLogs,
            name="report_logs",
        ),
        url(r"/reports", orderportal.report.Reports, name="reports"),
        url(r"/accounts", orderportal.account.Accounts, name="accounts"),
        url(
            r"/api/v1/accounts", orderportal.account.AccountsApiV1, name="accounts_api"
        ),
        url(r"/accounts.csv", orderportal.account.AccountsCsv, name="accounts_csv"),
        url(r"/accounts.xlsx", orderportal.account.AccountsXlsx, name="accounts_xlsx"),
        url(r"/account/([^/]+)", orderportal.account.Account, name="account"),
        url(
            r"/api/v1/account/([^/]+)",
            orderportal.account.AccountApiV1,
            name="account_api",
        ),
        url(
            r"/account/([^/]+)/orders",
            orderportal.account.AccountOrders,
            name="account_orders",
        ),
        url(
            r"/api/v1/account/([^/]+)/orders",
            orderportal.account.AccountOrdersApiV1,
            name="account_orders_api",
        ),
        url(
            r"/account/([^/]+)/groups/orders",
            orderportal.account.AccountGroupsOrders,
            name="account_groups_orders",
        ),
        url(
            r"/api/v1/account/([^/]+)/groups/orders",
            orderportal.account.AccountGroupsOrdersApiV1,
            name="account_groups_orders_api",
        ),
        url(
            r"/account/([^/]+)/logs",
            orderportal.account.AccountLogs,
            name="account_logs",
        ),
        url(
            r"/account/([^/]+)/messages",
            orderportal.account.AccountMessages,
            name="account_messages",
        ),
        url(
            r"/account/([^/]+)/edit",
            orderportal.account.AccountEdit,
            name="account_edit",
        ),
        url(constants.LOGIN_URL, orderportal.account.Login, name="login"),
        url(r"/logout", orderportal.account.Logout, name="logout"),
        url(r"/reset", orderportal.account.Reset, name="reset"),
        url(r"/password", orderportal.account.Password, name="password"),
        url(r"/register", orderportal.account.Register, name="register"),
        url(r"/registered", orderportal.account.Registered, name="registered"),
        url(
            r"/account/([^/]+)/enable",
            orderportal.account.AccountEnable,
            name="account_enable",
        ),
        url(
            r"/account/([^/]+)/disable",
            orderportal.account.AccountDisable,
            name="account_disable",
        ),
        url(
            r"/account/([^/]+)/updateinfo",
            orderportal.account.AccountUpdateInfo,
            name="account_update_info",
        ),
        url(r"/group/([0-9a-f]{32})", orderportal.group.Group, name="group"),
        url(r"/group", orderportal.group.GroupCreate, name="group_create"),
        url(
            r"/group/([0-9a-f]{32})/edit",
            orderportal.group.GroupEdit,
            name="group_edit",
        ),
        url(
            r"/group/([0-9a-f]{32})/accept",
            orderportal.group.GroupAccept,
            name="group_accept",
        ),
        url(
            r"/group/([0-9a-f]{32})/decline",
            orderportal.group.GroupDecline,
            name="group_decline",
        ),
        url(
            r"/group/([0-9a-f]{32})/logs",
            orderportal.group.GroupLogs,
            name="group_logs",
        ),
        url(r"/groups", orderportal.group.Groups, name="groups"),
        url(r"/forms", orderportal.form.Forms, name="forms"),
        url(r"/form/([0-9a-f]{32})", orderportal.form.Form, name="form"),
        url(
            r"/api/v1/form/([0-9a-f]{32})", orderportal.form.FormApiV1, name="form_api"
        ),
        url(r"/form/([0-9a-f]{32})/logs", orderportal.form.FormLogs, name="form_logs"),
        url(r"/form", orderportal.form.FormCreate, name="form_create"),
        url(r"/form/([0-9a-f]{32})/edit", orderportal.form.FormEdit, name="form_edit"),
        url(
            r"/form/([0-9a-f]{32})/clone", orderportal.form.FormClone, name="form_clone"
        ),
        url(
            r"/form/([0-9a-f]{32})/pending",
            orderportal.form.FormPending,
            name="form_pending",
        ),
        url(
            r"/form/([0-9a-f]{32})/testing",
            orderportal.form.FormTesting,
            name="form_testing",
        ),
        url(
            r"/form/([0-9a-f]{32})/enable",
            orderportal.form.FormEnable,
            name="form_enable",
        ),
        url(
            r"/form/([0-9a-f]{32})/disable",
            orderportal.form.FormDisable,
            name="form_disable",
        ),
        url(
            r"/form/([0-9a-f]{32})/field",
            orderportal.form.FormFieldCreate,
            name="field_create",
        ),
        url(
            r"/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)",
            orderportal.form.FormFieldEdit,
            name="field_edit",
        ),
        url(
            r"/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)/descr",
            orderportal.form.FormFieldEditDescr,
            name="field_edit_descr",
        ),
        url(
            r"/form/([0-9a-f]{32})/orders",
            orderportal.form.FormOrders,
            name="form_orders",
        ),
        url(
            r"/form/([0-9a-f]{32})/aggregate",
            orderportal.form.FormAggregate,
            name="form_aggregate",
        ),
        url(r"/infos", orderportal.info.Infos, name="infos"),
        url(r"/info", orderportal.info.InfoCreate, name="info_create"),
        url(r"/info/([^/]+)", orderportal.info.Info, name="info"),
        url(r"/info/([^/]+)/edit", orderportal.info.InfoEdit, name="info_edit"),
        url(r"/info/([^/]+)/logs", orderportal.info.InfoLogs, name="info_logs"),
        url(r"/files", orderportal.file.Files, name="files"),
        url(r"/file", orderportal.file.FileCreate, name="file_create"),
        url(r"/file/([^/]+)", orderportal.file.File, name="file"),
        url(
            r"/file/([^/]+)/download",
            orderportal.file.FileDownload,
            name="file_download",
        ),
        url(r"/file/([^/]+)/edit", orderportal.file.FileEdit, name="file_edit"),
        url(
            r"/api/v1/file/([^/]+)/edit",
            orderportal.file.FileEditApiV1,
            name="file_edit_api",
        ),
        url(r"/file/([0-9a-f]{32})/logs", orderportal.file.FileLogs, name="file_logs"),
        url(r"/admin/texts", orderportal.admin.Texts, name="texts"),
        url(r"/admin/text/([^/]+)", orderportal.admin.TextEdit, name="text_edit"),
        url(
            r"/admin/order_statuses",
            orderportal.admin.OrderStatuses,
            name="admin_order_statuses",
        ),
        url(
            r"/admin/orders_list",
            orderportal.admin.OrdersList,
            name="admin_orders_list",
        ),
        url(
            r"/admin/order_status/([^/]+)/enable",
            orderportal.admin.OrderStatusEnable,
            name="order_status_enable",
        ),
        url(
            r"/admin/order_status/([^/]+)",
            orderportal.admin.OrderStatusEdit,
            name="admin_order_status_edit",
        ),
        url(
            r"/admin/order_transitions/([^/]+)",
            orderportal.admin.OrderTransitionsEdit,
            name="admin_order_transitions_edit",
        ),
        url(
            r"/admin/site_configuration",
            orderportal.admin.SiteConfiguration,
            name="admin_site_configuration",
        ),
        url(
            r"/admin/order_configuration",
            orderportal.admin.OrderConfiguration,
            name="admin_order_configuration",
        ),
        url(
            r"/admin/order_messages",
            orderportal.admin.OrderMessages,
            name="admin_order_messages",
        ),
        url(
            r"/admin/order_message_edit/([^/]+)",
            orderportal.admin.OrderMessageEdit,
            name="admin_order_message_edit",
        ),
        url(r"/admin/account", orderportal.admin.Account, name="admin_account"),
        url(
            r"/admin/account_messages",
            orderportal.admin.AccountMessages,
            name="admin_account_messages",
        ),
        url(
            r"/admin/account_message/([^/]+)",
            orderportal.admin.AccountMessageEdit,
            name="admin_account_message_edit",
        ),
        url(
            r"/admin/display_configuration",
            orderportal.admin.DisplayConfiguration,
            name="admin_display_configuration",
        ),
        url(
            r"/admin/statistics", orderportal.admin.Statistics, name="admin_statistics"
        ),
        url(r"/admin/database", orderportal.admin.Database, name="admin_database"),
        url(r"/admin/document/(.+)", orderportal.admin.Document, name="admin_document"),
        url(r"/admin/settings", orderportal.admin.Settings, name="admin_settings"),
        url(r"/search", orderportal.search.Search, name="search"),
        url(r"/site/([^/]+)", orderportal.home.SiteFile, name="site"),
        url(r"/api/v1/(.*)", orderportal.home.NoSuchEntityApiV1),
        url(r"/(.*)", orderportal.home.NoSuchEntity),
    ]


def main():
    orderportal.config.load_settings_from_file()
    db = orderportal.database.get_db()
    orderportal.database.update_design_documents(db)
    orderportal.admin.migrate_meta_documents(db)
    orderportal.admin.migrate_text_documents(db)
    orderportal.config.load_settings_from_db(db)
    orderportal.config.load_texts_from_db(db)

    if settings["BASE_URL_PATH_PREFIX"]:
        login_url = f"/{settings['BASE_URL_PATH_PREFIX']}{constants.LOGIN_URL}"
    else:
        login_url = constants.LOGIN_URL

    application = tornado.web.Application(
        handlers=get_handlers(),
        debug=settings.get("TORNADO_DEBUG", False),
        autoreload=settings.get("TORNADO_DEBUG", False),
        cookie_secret=settings["COOKIE_SECRET"],
        xsrf_cookies=True,
        ui_modules=orderportal.uimodules,
        template_path=constants.TEMPLATE_DIR,
        static_path=constants.STATIC_DIR,
        login_url=login_url,
    )
    application.listen(settings["PORT"], xheaders=True)

    # Add href URLs for the status icons.
    for key, value in settings["ORDER_STATUSES_LOOKUP"].items():
        value["href"] = f"/static/{key}.png"

    url = settings["BASE_URL"]
    if settings["BASE_URL_PATH_PREFIX"]:
        url += settings["BASE_URL_PATH_PREFIX"]
    logging.getLogger("orderportal").info(f"Web server at {url}")

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
