"OrderPortal web application server."

import logging
import os
import sys

import tornado.web
import tornado.ioloop

from orderportal import constants
from orderportal import settings, parameters
from orderportal import utils

import orderportal.account
import orderportal.admin
import orderportal.designs
import orderportal.event
import orderportal.file
import orderportal.form
import orderportal.group
import orderportal.home
import orderportal.info
import orderportal.news
import orderportal.order
import orderportal.search
import orderportal.uimodules


def main():
    if len(sys.argv) == 2:
        filepath = sys.argv[1]
    else:
        filepath = None
    utils.get_settings(filepath=filepath)
    db = utils.get_db()
    orderportal.designs.update_design_documents(db)
    orderportal.admin.update_meta_documents(db)
    orderportal.admin.load_texts(db)
    orderportal.admin.load_order_statuses(db)

    url = tornado.web.url
    handlers = [
        url(r"/", orderportal.home.Home, name="home"),
        url(r"/status", orderportal.home.Status, name="status"),
        url(r"/contact", orderportal.home.Contact, name="contact"),
        url(r"/about", orderportal.home.About, name="about"),
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
        url(
            r"/order/([0-9a-f]{32})/report",
            orderportal.order.OrderReport,
            name="order_report",
        ),
        url(
            r"/api/v1/order/([0-9a-f]{32})/report",
            orderportal.order.OrderReportApiV1,
            name="order_report_api",
        ),
        url(
            r"/order/([0-9a-f]{32})/report/edit",
            orderportal.order.OrderReportEdit,
            name="order_report_edit",
        ),
        url(r"/orders", orderportal.order.Orders, name="orders"),
        url(r"/api/v1/orders", orderportal.order.OrdersApiV1, name="orders_api"),
        url(r"/orders.csv", orderportal.order.OrdersCsv, name="orders_csv"),
        url(r"/orders.xlsx", orderportal.order.OrdersXlsx, name="orders_xlsx"),
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
        url(r"/login", orderportal.account.Login, name="login"),
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
            orderportal.form.FormOrdersAggregate,
            name="form_orders_aggregate",
        ),
        url(r"/news", orderportal.news.News, name="news"),
        url(r"/new", orderportal.news.NewsCreate, name="news_create"),
        url(r"/new/([0-9a-f]{32})", orderportal.news.NewsEdit, name="news_edit"),
        url(r"/events", orderportal.event.Events, name="events"),
        url(r"/event/([0-9a-f]{32})", orderportal.event.EventEdit, name="event_edit"),
        url(r"/event", orderportal.event.EventCreate, name="event_create"),
        url(r"/infos", orderportal.info.Infos, name="infos"),
        url(r"/info", orderportal.info.InfoCreate, name="info_create"),
        url(r"/info/([^/]+)", orderportal.info.Info, name="info"),
        url(r"/info/([^/]+)/edit", orderportal.info.InfoEdit, name="info_edit"),
        url(r"/info/([^/]+)/logs", orderportal.info.InfoLogs, name="info_logs"),
        url(r"/files", orderportal.file.Files, name="files"),
        url(r"/file", orderportal.file.FileCreate, name="file_create"),
        url(r"/file/([^/]+)", orderportal.file.File, name="file"),
        url(r"/file/([^/]+)/meta", orderportal.file.FileMeta, name="file_meta"),
        url(r"/file/([^/]+)/edit", orderportal.file.FileEdit, name="file_edit"),
        url(
            r"/api/v1/file/([^/]+)/edit",
            orderportal.file.FileEditApiV1,
            name="file_edit_api",
        ),
        url(
            r"/file/([^/]+)/download",
            orderportal.file.FileDownload,
            name="file_download",
        ),
        url(r"/file/([0-9a-f]{32})/logs", orderportal.file.FileLogs, name="file_logs"),
        url(r"/admin/text/([^/]+)", orderportal.admin.Text, name="text"),
        url(r"/admin/texts", orderportal.admin.Texts, name="texts"),
        url(r"/admin/settings", orderportal.admin.Settings, name="settings"),
        url(
            r"/admin/order_statuses",
            orderportal.admin.OrderStatuses,
            name="admin_order_statuses",
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
            r"/admin/order_messages",
            orderportal.admin.OrderMessages,
            name="admin_order_messages",
        ),
        url(
            r"/admin/account_messages",
            orderportal.admin.AccountMessages,
            name="admin_account_messages",
        ),
        url(r"/search", orderportal.search.Search, name="search"),
        url(
            r"/site/([^/]+)",
            tornado.web.StaticFileHandler,
            {"path": settings["SITE_STATIC_DIR"]},
            name="site",
        ),
        url(r"/api/v1/(.*)", orderportal.home.NoSuchEntityApiV1),
        url(r"/(.*)", orderportal.home.NoSuchEntity),
    ]

    application = tornado.web.Application(
        handlers=handlers,
        debug=settings.get("TORNADO_DEBUG", False),
        autoreload=settings.get("TORNADO_DEBUG", False),
        cookie_secret=settings["COOKIE_SECRET"],
        xsrf_cookies=True,
        ui_modules=orderportal.uimodules,
        template_path=os.path.join(constants.ROOT, "templates"),
        static_path=os.path.join(constants.ROOT, "static"),
        login_url=(settings["BASE_URL_PATH_PREFIX"] or "") + "/login",
    )

    # Add href URLs for the status icons.
    for key, value in parameters["ORDER_STATUSES_LOOKUP"].items():
        value["href"] = f"/static/{key}.png"

    application.listen(settings["PORT"], xheaders=True)
    url = settings["BASE_URL"]
    if settings["BASE_URL_PATH_PREFIX"]:
        url += settings["BASE_URL_PATH_PREFIX"]
    pid = os.getpid()
    if settings["PIDFILE"]:
        with open(settings["PIDFILE"], "w") as pf:
            pf.write(str(pid))
    logging.info(f"web server PID {pid} at {url}")

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
