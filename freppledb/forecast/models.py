#
# Copyright (C) 2023 by frePPLe bv
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from collections import OrderedDict
from datetime import date, datetime
from dateutil.parser import parse
from itertools import chain
import json
from logging import INFO, ERROR, WARNING, DEBUG
from openpyxl.worksheet.cell_range import CellRange
from openpyxl.worksheet.worksheet import Worksheet
import os
import random
import requests
from threading import local

from django.conf import settings
from django.core import management
from django.core.exceptions import ValidationError
from django.db import models, DEFAULT_DB_ALIAS, connections
from django.db.models import Case, When, Value
from django.utils import translation
from django.utils.encoding import force_str
from django.utils.translation import pgettext, gettext_lazy as _

from freppledb.common.auth import getWebserviceAuthorization
from freppledb.common.models import AuditModel, BucketDetail, Parameter
from freppledb.input.models import Customer, Item, Location, Operation
from freppledb.webservice.utils import useWebService


class Forecast(AuditModel):
    # Forecasting methods
    methods = (
        ("automatic", _("Automatic")),
        ("constant", pgettext("forecast method", "Constant")),
        ("trend", pgettext("forecast method", "Trend")),
        ("seasonal", pgettext("forecast method", "Seasonal")),
        ("intermittent", pgettext("forecast method", "Intermittent")),
        ("moving average", pgettext("forecast method", "Moving average")),
        ("manual", _("Manual")),
        ("aggregate", _("Aggregate")),
    )

    # Database fields
    name = models.CharField(_("name"), max_length=300, primary_key=True)
    description = models.CharField(
        _("description"), max_length=500, null=True, blank=True
    )
    category = models.CharField(
        _("category"), max_length=300, null=True, blank=True, db_index=True
    )
    subcategory = models.CharField(
        _("subcategory"), max_length=300, null=True, blank=True, db_index=True
    )
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"), db_index=True, on_delete=models.CASCADE
    )
    item = models.ForeignKey(
        Item, verbose_name=_("item"), db_index=True, on_delete=models.CASCADE
    )
    location = models.ForeignKey(
        Location, verbose_name=_("location"), db_index=True, on_delete=models.CASCADE
    )
    method = models.CharField(
        _("Forecast method"),
        max_length=20,
        null=True,
        blank=True,
        choices=methods,
        default="automatic",
        help_text=_("Method used to generate a base forecast"),
    )
    priority = models.IntegerField(
        _("priority"),
        default=10,
        help_text=_(
            "Priority of the demand (lower numbers indicate more important demands)"
        ),
    )
    minshipment = models.DecimalField(
        _("minimum shipment"),
        null=True,
        blank=True,
        max_digits=20,
        decimal_places=8,
        help_text=_("Minimum shipment quantity when planning this demand"),
    )
    maxlateness = models.DurationField(
        _("maximum lateness"),
        null=True,
        blank=True,
        help_text=_("Maximum lateness allowed when planning this demand"),
    )
    discrete = models.BooleanField(
        _("discrete"), default=True, help_text=_("Round forecast numbers to integers")
    )
    out_smape = models.DecimalField(
        _("estimated forecast error"),
        null=True,
        blank=True,
        max_digits=20,
        decimal_places=8,
    )
    out_method = models.CharField(
        _("calculated forecast method"), max_length=20, null=True, blank=True
    )
    out_deviation = models.DecimalField(
        _("calculated standard deviation"),
        null=True,
        blank=True,
        max_digits=20,
        decimal_places=8,
    )
    planned = models.BooleanField(
        _("planned"),
        default=True,
        null=False,
        help_text=_("Specifies whether this forecast record should be planned"),
    )
    operation = models.ForeignKey(
        Operation,
        verbose_name=_("delivery operation"),
        null=True,
        blank=True,
        related_name="used_forecast",
        on_delete=models.SET_NULL,
        help_text=_("Operation used to satisfy this demand"),
    )

    class Meta(AuditModel.Meta):
        db_table = "forecast"
        verbose_name = _("forecast")
        verbose_name_plural = _("forecasts")
        ordering = ["name"]
        unique_together = (("item", "location", "customer"),)

    def __str__(self):
        return self.name

    @classmethod
    def beforeUpload(cls, database=DEFAULT_DB_ALIAS):
        # Assure the hierarchies are up to date and have only single root
        # This also creates the dummy parent root if required
        Item.createRootObject(database=database)
        Location.createRootObject(database=database)
        Customer.createRootObject(database=database)

    @staticmethod
    def flush(session, mode, database=DEFAULT_DB_ALIAS):
        if "FREPPLE_TEST" in os.environ:
            server = settings.DATABASES[database]["TEST"]["FREPPLE_PORT"]
        else:
            server = settings.DATABASES[database]["FREPPLE_PORT"]
        response = session.post(
            "http://%s/flush/%s/" % (server, mode),
            headers={
                "Authorization": "Bearer %s"
                % getWebserviceAuthorization(
                    sub="admin",
                    sid=1,
                    exp=3600,
                    aud="*",
                ),
                "Content-Type": "application/json",
                "content-length": "0",
            },
        )
        if response.status_code != 200:
            raise Exception(response.text)

    @staticmethod
    def updatePlan(
        startdate=None,
        enddate=None,
        database=DEFAULT_DB_ALIAS,
        forecast=None,
        item=None,
        customer=None,
        location=None,
        request=None,
        session=None,
        token=None,
        **kwargs
    ):
        if not kwargs:
            return
        data = {}
        if item:
            data["item"] = item
        if location:
            data["location"] = location
        if customer:
            data["customer"] = customer
        if forecast:
            data["forecast"] = forecast
        if "FREPPLE_TEST" in os.environ:
            server = settings.DATABASES[database]["TEST"]["FREPPLE_PORT"]
        else:
            server = settings.DATABASES[database]["FREPPLE_PORT"]
        if startdate:
            if isinstance(startdate, (date, datetime)):
                data["startdate"] = startdate.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Guess! the date format, using Month-Day-Year as preference
                # to resolve ambiguity.
                # This default style is also the default datestyle in Postgres
                # https://www.postgresql.org/docs/9.1/runtime-config-client.html#GUC-DATESTYLE
                data["startdate"] = parse(
                    startdate, yearfirst=False, dayfirst=False
                ).strftime("%Y-%m-%dT%H:%M:%S")
        if enddate:
            if isinstance(enddate, (date, datetime)):
                data["enddate"] = enddate.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Guess! the date format, using Month-Day-Year as preference
                # to resolve ambiguity.
                # This default style is also the default datestyle in Postgres
                # https://www.postgresql.org/docs/9.1/runtime-config-client.html#GUC-DATESTYLE
                data["enddate"] = parse(
                    enddate, yearfirst=False, dayfirst=False
                ).strftime("%Y-%m-%dT%H:%M:%S")
        for m, val in kwargs.items():
            if val is not None:
                data[m] = float(val)
        my_session = session or requests.Session()
        my_token = token or getWebserviceAuthorization(
            sub=request.user.username if request else "admin",
            sid=request.user.id if request else 1,
            exp=3600,
            aud="*",
        )
        try:
            payload = json.dumps({"forecast": [data]}).encode("utf-8")
            response = my_session.post(
                "http://%s/json" % server,
                data=payload,
                headers={
                    "Authorization": "Bearer %s" % my_token,
                    "Content-Type": "application/json",
                    "content-length": str(len(payload)),
                },
            )
            if response.status_code != 200:
                raise Exception(response.text)
        finally:
            if not session:
                my_session.close()


class PropertyField:
    """
    A class to define a computed field on a Django model.
    The model is exposed a property on model instances, and the get
    and set methods are used to store and retrieve the values.
    """

    type = "number"
    editable = False
    name = None
    verbose_name = None
    export = True
    choices = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if key == "type" and value not in (
                "string",
                "boolean",
                "number",
                "integer",
                "date",
                "datetime",
                "duration",
                "time",
            ):
                raise Exception("Invalid property type '%s'." % value)
            else:
                setattr(self, key, value)
        if not self.name:
            raise Exception("Missing property name.")
        if not self.verbose_name:
            self.verbose_name = self.name


class ForecastPlan(models.Model):

    # Model managers
    objects = models.Manager()  # The default model manager

    @classmethod
    def export_objects(cls, query, request):
        return query.extra(
            select={
                m.name: "(value->>'%s')::numeric" % m.name
                for m in chain(
                    Measure.standard_measures(), Measure.objects.using(request.database)
                )
            },
            where=[
                """
                exists (
                select 1
                from forecast
                where forecastplan.item_id = forecast.item_id
                and forecastplan.customer_id = forecast.customer_id
                and forecastplan.location_id = forecast.location_id)
                """
            ],
        ).order_by("item", "location", "customer", "startdate")

    # The forecast plan model also depends on the bucket detail table.
    # The database constraints don't reflect that, so we need to define it explicitly.
    extra_dependencies = [BucketDetail, Forecast]

    # Database fields
    id = models.AutoField(_("identifier"), primary_key=True)
    item = models.ForeignKey(
        Item,
        verbose_name=_("item"),
        null=False,
        db_index=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
    )
    location = models.ForeignKey(
        Location,
        verbose_name=_("location"),
        null=False,
        db_index=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
    )
    customer = models.ForeignKey(
        Customer,
        verbose_name=_("customer"),
        null=False,
        db_index=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
    )
    startdate = models.DateTimeField(_("start date"), null=False, db_index=True)
    enddate = models.DateTimeField(_("end date"), null=False)
    value = models.JSONField(default=dict, blank=False, null=False)

    # Property fields
    # TODO this syntax for defining properties isn't as slick and clean as it could be.
    # Ideally we want some form of syntax as the above for Django fields.
    @staticmethod
    def propertyFields(request):
        return [
            PropertyField(
                name=m.name,
                verbose_name=m.description,
                editable=m.editable,
                type="number",
            )
            for m in chain(
                Measure.standard_measures(),
                Measure.objects.all().using(request.database),
            )
        ] + [
            # Used during import
            PropertyField(
                name="forecast",
                verbose_name=_("forecast"),
                editable=True,
                type="string",
                export=False,
            ),
            PropertyField(
                name="bucket",
                verbose_name=_("bucket"),
                editable=True,
                type="string",
                export=False,
            ),
            PropertyField(
                name="datafield",
                verbose_name=_("data field"),
                editable=True,
                type="string",
                export=False,
            ),
        ]

    def __str__(self):
        return "%s - %s - %s - %s" % (
            self.item,
            self.location,
            self.customer,
            str(self.startdate),
        )

    class Meta:
        db_table = "forecastplan"
        ordering = ["id"]
        verbose_name = _("forecast plan")
        verbose_name_plural = _("forecast plans")
        constraints = [
            models.UniqueConstraint(
                fields=["item", "location", "customer", "startdate"],
                name="forecastplan_uidx",
            )
        ]
        managed = False

    @staticmethod
    def parseData(data, rowmapper, user, database, ping, excel_duration_in_days=False):
        """
        This method is called when importing forecast data through a CSV
        or Excel file.
        """
        warnings = 0
        changed = 0
        errors = 0
        rownumber = 0
        processed_header = False
        rowWrapper = rowmapper()
        headers = []
        measures = []
        pivotbuckets = None
        session = None
        token = None

        # Read the name of all buckets in memory
        # We use an ordered dict in case Excel contains dates instead of bucket names
        # to be able to use first the forecast.calendar bucket
        bucket_names = OrderedDict()
        forecast_calendar = Parameter.getValue("forecast.calendar", database, "month")

        for i in (
            BucketDetail.objects.all()
            .using(database)
            .only("name", "startdate", "enddate")
            .annotate(
                custom_order=Case(
                    When(bucket=forecast_calendar, then=Value(1)), default=Value(2)
                )
            )
            .order_by("custom_order")
        ):
            bucket_names[i.name.lower()] = (
                i.startdate,
                i.enddate,
            )

        # Need to assure that the web service is up and running
        if useWebService(database):
            try:
                # We need a trick to enforce using a new database connection and transaction
                tmp = connections._connections
                connections._connections = local()
                management.call_command("runwebservice", database=database, wait=True)
                connections._connections = tmp
            except management.base.CommandError:
                yield (ERROR, None, None, None, "Web service didn't start")
                raise StopIteration
        else:
            yield (ERROR, None, None, None, "Web service not activated")
            raise StopIteration

        # Detect excel autofilter data tables
        if isinstance(data, Worksheet) and data.auto_filter.ref:
            bounds = CellRange(data.auto_filter.ref).bounds
        else:
            bounds = None

        for row in data:
            rownumber += 1
            if bounds:
                # Only process data in the excel auto-filter range
                if rownumber < bounds[1]:
                    continue
                elif rownumber > bounds[3]:
                    break
                else:
                    rowWrapper.setData(row)
            else:
                rowWrapper.setData(row)

            # Case 1: Process the header row
            if not processed_header:
                processed_header = True
                colnum = 1
                for col in rowWrapper.values():
                    if isinstance(col, datetime):
                        for bucket in bucket_names:
                            if (
                                col >= bucket_names[bucket][0]
                                and col < bucket_names[bucket][1]
                            ):
                                col = bucket
                                break

                    col = str(col).strip().strip("#").lower() if col else ""

                    ok = False
                    if pivotbuckets is not None:
                        try:
                            (startdate, enddate) = bucket_names[col]
                            headers.append(
                                PropertyField(name=col, editable=True, type="string")
                            )
                            pivotbuckets.append((col, startdate, enddate))
                        except KeyError:
                            headers.append(None)
                            yield (
                                WARNING,
                                None,
                                None,
                                None,
                                force_str(
                                    _("Bucket '%(name)s' not found") % {"name": col}
                                ),
                            )
                        continue
                    for i in chain(
                        ForecastPlan._meta.fields,
                        Measure.standard_measures(),
                        Measure.objects.all().using(database),
                        [
                            # Dummy fields used during import
                            PropertyField(
                                name="forecast",
                                verbose_name=_("forecast"),
                                editable=True,
                                type="string",
                                export=False,
                            ),
                            PropertyField(
                                name="bucket",
                                verbose_name=_("bucket"),
                                editable=True,
                                type="string",
                                export=False,
                            ),
                            PropertyField(
                                name="datafield",
                                verbose_name=_("data field"),
                                editable=True,
                                type="string",
                                export=False,
                            ),
                            PropertyField(
                                name="multiplier",
                                verbose_name=_("multiplier"),
                                editable=True,
                                type="number",
                                export=False,
                            ),
                        ],
                    ):
                        # Try with translated field names
                        if (
                            col == i.name.lower()
                            or col == i.verbose_name.lower()
                            or col
                            == (
                                "%s - %s" % (ForecastPlan.__name__, i.verbose_name)
                            ).lower()
                        ):
                            if i.name == "datafield":
                                pivotbuckets = []
                                headers.append(i)
                            elif i.editable is True:
                                headers.append(i)
                                if isinstance(i, Measure):
                                    measures.append(i)
                            else:
                                headers.append(None)
                            ok = True
                            break
                        if translation.get_language() != "en":
                            # Try with English field names
                            with translation.override("en"):
                                if (
                                    col == i.name.lower()
                                    or col == i.verbose_name.lower()
                                    or col
                                    == (
                                        "%s - %s"
                                        % (ForecastPlan.__name__, i.verbose_name)
                                    ).lower()
                                ):
                                    if i.name == "datafield":
                                        pivotbuckets = []
                                        headers.append(i)
                                    elif i.editable is True:
                                        headers.append(i)
                                        if isinstance(i, Measure):
                                            measures.append(i)
                                    else:
                                        headers.append(None)
                                    ok = True
                                    break
                    if not ok:
                        headers.append(None)
                        warnings += 1
                        yield (
                            WARNING,
                            None,
                            None,
                            None,
                            force_str(
                                _(
                                    "Skipping unknown field %(column)s"
                                    % {"column": '"%s"' % col}
                                )
                            ),
                        )
                    colnum += 1
                rowWrapper = rowmapper(headers)

                # Check required fields
                fields = [i.name for i in headers if i]
                hasforecastfield = "forecast" in fields
                missing = []
                if not hasforecastfield:
                    for k in ["item", "customer", "location"]:
                        if k not in fields:
                            missing.append(k)
                if (
                    "startdate" not in fields
                    and "enddate" not in fields
                    and "bucket" not in fields
                    and pivotbuckets is None
                ):
                    missing.append("startdate")
                if missing:
                    errors += 1
                    yield (
                        ERROR,
                        None,
                        None,
                        None,
                        _(
                            "Some keys were missing: %(keys)s"
                            % {"keys": ", ".join(missing)}
                        ),
                    )
                if pivotbuckets:
                    measures = [
                        m
                        for m in chain(
                            Measure.standard_measures(),
                            Measure.objects.all().using(database),
                        )
                        if m.editable
                    ]
                elif not measures:
                    # Check the presence of editable fields
                    warnings += 1
                    yield (WARNING, None, None, None, _("No editable fields found"))
                    raise StopIteration

                # Initialize http connection
                session = requests.Session()
                token = getWebserviceAuthorization(
                    sub=user.username if user else "admin",
                    sid=user.id if user else 1,
                    exp=3600,
                    aud="*",
                )
                Forecast.flush(session, mode="manual", database=database)

            # Case 2: Skip empty rows
            elif rowWrapper.empty():
                continue

            # Case 3: Process a data row
            else:
                # Send a ping-alive message to make the upload interruptable
                if ping:
                    if rownumber % 50 == 0:
                        yield (DEBUG, rownumber, None, None, None)

                multiplier = rowWrapper.get("multiplier") or 1

                # Call the update method
                if pivotbuckets:
                    # Upload in pivot layout
                    fieldname = rowWrapper.get("datafield", "").lower()
                    field = None
                    for m in measures:
                        if (
                            fieldname == m.verbose_name.lower()
                            or fieldname == m.name.lower()
                        ):
                            field = m
                            break
                    if not field:
                        # Irrelevant data field
                        continue
                    for col, startdate, enddate in pivotbuckets:
                        try:
                            val = rowWrapper.get(col, None)
                            if val is not None and val != "":
                                Forecast.updatePlan(
                                    startdate=startdate,
                                    enddate=enddate,
                                    database=database,
                                    forecast=rowWrapper.get("forecast", None),
                                    item=rowWrapper.get("item", None),
                                    location=rowWrapper.get("location", None),
                                    customer=rowWrapper.get("customer", None),
                                    session=session,
                                    token=token,
                                    **{field.name: val * multiplier}
                                )
                                changed += 1
                        except Exception as e:
                            errors += 1
                            yield (ERROR, rownumber, field, val, str(e))
                else:
                    # Upload in list layout
                    try:
                        # Find the time bucket
                        bucket = rowWrapper.get("bucket", None)
                        if bucket:
                            if isinstance(bucket, datetime):
                                startdate = None
                                enddate = None
                                for buck in bucket_names:
                                    if (
                                        bucket >= bucket_names[buck][0]
                                        and bucket < bucket_names[buck][1]
                                    ):
                                        startdate = bucket_names[buck][0]
                                        enddate = bucket_names[buck][1]
                                        break
                            else:
                                b = bucket_names.get(bucket.lower(), None)
                                if b:
                                    startdate = b[0]
                                    enddate = b[1]
                                else:
                                    startdate = rowWrapper.get("startdate", None)
                                    enddate = rowWrapper.get("enddate", None)
                        else:
                            startdate = rowWrapper.get("startdate", None)
                            enddate = rowWrapper.get("enddate", None)

                        Forecast.updatePlan(
                            startdate=startdate,
                            enddate=enddate,
                            database=database,
                            forecast=rowWrapper.get("forecast", None),
                            item=rowWrapper.get("item", None),
                            location=rowWrapper.get("location", None),
                            customer=rowWrapper.get("customer", None),
                            session=session,
                            token=token,
                            **{
                                m.name: rowWrapper.get(m.name) * multiplier
                                if rowWrapper.get(m.name) is not None
                                and rowWrapper.get(m.name) != ""
                                else None
                                for m in measures
                            }
                        )
                        changed += 1
                    except Exception as e:
                        errors += 1
                        yield (ERROR, rownumber, None, None, str(e))

        if session:
            Forecast.flush(session, mode="auto", database=database)
            session.close()
        yield (
            INFO,
            None,
            None,
            None,
            _(
                "%(rows)d data rows, changed %(changed)d and added %(added)d records, %(errors)d errors, %(warnings)d warnings"
            )
            % {
                "rows": rownumber - 1,
                "changed": changed,
                "added": 0,
                "errors": errors,
                "warnings": warnings,
            },
        )


class Measure(AuditModel):
    obfuscate = False

    @classmethod
    def standard_measures(cls):
        if not hasattr(cls, "_standardmeasures"):
            cls._standardmeasures = (
                # Measures computed in the backend
                # TODO the past, future and outlier measures need to be defined
                # first: that's unfortunately hardcoded in the forecast report grid
                Measure(
                    name="past",
                    mode_past="hide",
                    mode_future="hide",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="future",
                    mode_past="hide",
                    mode_future="hide",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="outlier",
                    mode_past="hide",
                    mode_future="hide",
                    computed="backend",
                    initially_hidden=True,
                ),
                # Measures computed in the frontend
                Measure(
                    name="orderstotal3ago",
                    type="aggregate",
                    label=_("total orders 3 years ago"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    computed="frontend",
                ),
                Measure(
                    name="ordersadjustment3ago",
                    type="aggregate",
                    label=_("orders adjustment 3 years ago"),
                    mode_future="edit",
                    mode_past="hide",
                    formatter="number",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="orderstotalvalue3ago",
                    type="aggregate",
                    label=_("total orders value 3 years ago"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="currency",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="ordersadjustmentvalue3ago",
                    type="aggregate",
                    label=_("orders adjustment value 3 years ago"),
                    mode_future="edit",
                    mode_past="hide",
                    formatter="currency",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="orderstotal2ago",
                    type="aggregate",
                    label=_("total orders 2 years ago"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    computed="frontend",
                ),
                Measure(
                    name="ordersadjustment2ago",
                    type="aggregate",
                    label=_("orders adjustment 2 years ago"),
                    mode_future="edit",
                    mode_past="hide",
                    formatter="number",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="orderstotalvalue2ago",
                    type="aggregate",
                    label=_("total orders value 2 years ago"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="currency",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="ordersadjustmentvalue2ago",
                    type="aggregate",
                    label=_("orders adjustment value 2 years ago"),
                    mode_future="edit",
                    mode_past="hide",
                    formatter="currency",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="orderstotal1ago",
                    type="aggregate",
                    label=_("total orders 1 years ago"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    computed="frontend",
                ),
                Measure(
                    name="ordersadjustment1ago",
                    type="aggregate",
                    label=_("orders adjustment 1 years ago"),
                    mode_future="edit",
                    mode_past="hide",
                    formatter="number",
                    computed="frontend",
                ),
                Measure(
                    name="orderstotalvalue1ago",
                    type="aggregate",
                    label=_("total orders value 1 years ago"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="currency",
                    computed="frontend",
                    initially_hidden=True,
                ),
                Measure(
                    name="ordersadjustmentvalue1ago",
                    type="aggregate",
                    label=_("orders adjustment value 1 years ago"),
                    mode_future="edit",
                    mode_past="hide",
                    formatter="currency",
                    computed="frontend",
                    initially_hidden=True,
                ),
                # Unit measures
                Measure(
                    name="orderstotal",
                    type="aggregate",
                    label=_("total orders"),
                    mode_future="view",
                    mode_past="view",
                    formatter="number",
                ),
                Measure(
                    name="ordersopen",
                    type="aggregate",
                    label=_("open orders"),
                    mode_future="view",
                    mode_past="view",
                    formatter="number",
                    initially_hidden=True,
                ),
                Measure(
                    name="ordersadjustment",
                    type="aggregate",
                    label=_("orders adjustment"),
                    mode_future="hide",
                    mode_past="edit",
                    formatter="number",
                ),
                Measure(
                    name="forecastbaseline",
                    type="aggregate",
                    label=_("forecast baseline"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                ),
                Measure(
                    name="forecastoverride",
                    type="aggregate",
                    label=_("forecast override"),
                    mode_future="edit",
                    mode_past="view",
                    defaultvalue=-1,
                    formatter="number",
                ),
                Measure(
                    name="forecastnet",
                    type="aggregate",
                    label=_("forecast net"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    initially_hidden=True,
                ),
                Measure(
                    name="forecastconsumed",
                    type="aggregate",
                    label=_("forecast consumed"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    initially_hidden=True,
                ),
                Measure(
                    name="ordersplanned",
                    type="aggregate",
                    label=_("planned orders"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    initially_hidden=True,
                ),
                Measure(
                    name="forecastplanned",
                    type="aggregate",
                    label=_("planned net forecast"),
                    mode_future="view",
                    mode_past="hide",
                    formatter="number",
                    initially_hidden=True,
                ),
                # Measures computed in the backend
                Measure(
                    name="backlogorder",
                    type="aggregate",
                    label=_("order backlog"),
                    mode_past="view",
                    mode_future="view",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="backlogforecast",
                    type="aggregate",
                    label=_("forecast backlog"),
                    mode_past="view",
                    mode_future="view",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="backlog",
                    type="aggregate",
                    label=_("backlog"),
                    mode_past="view",
                    mode_future="view",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="totaldemand",
                    type="aggregate",
                    label=_("total demand"),
                    mode_past="view",
                    mode_future="view",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="totalsupply",
                    type="aggregate",
                    label=_("total supply"),
                    mode_past="view",
                    mode_future="view",
                    computed="backend",
                    initially_hidden=True,
                ),
                Measure(
                    name="backlogordervalue",
                    type="aggregate",
                    label=_("order backlog value"),
                    mode_past="view",
                    mode_future="view",
                    formatter="currency",
                    initially_hidden=True,
                    computed="backend",
                ),
                Measure(
                    name="backlogforecastvalue",
                    type="aggregate",
                    label=_("forecast backlog value"),
                    mode_past="view",
                    mode_future="view",
                    formatter="currency",
                    initially_hidden=True,
                    computed="backend",
                ),
                Measure(
                    name="backlogvalue",
                    type="aggregate",
                    label=_("backlog value"),
                    mode_past="view",
                    mode_future="view",
                    formatter="currency",
                    initially_hidden=True,
                    computed="backend",
                ),
                Measure(
                    name="totaldemandvalue",
                    type="aggregate",
                    label=_("total demand value"),
                    mode_past="view",
                    mode_future="view",
                    formatter="currency",
                    initially_hidden=True,
                    computed="backend",
                ),
                Measure(
                    name="totalsupplyvalue",
                    type="aggregate",
                    label=_("total supply value"),
                    mode_past="view",
                    mode_future="view",
                    formatter="currency",
                    initially_hidden=True,
                    computed="backend",
                ),
            )
        return cls._standardmeasures

    # Types of measures.
    types = (
        ("aggregate", _("aggregate")),
        ("local", _("local")),
        ("computed", _("computed")),
    )
    modes = (("edit", _("edit")), ("view", _("view")), ("hide", _("hide")))
    formatters = (("number", _("number")), ("currency", _("currency")))

    # Database fields
    name = models.CharField(
        _("name"), max_length=300, primary_key=True, help_text=_("Unique identifier")
    )
    label = models.CharField(
        _("label"),
        max_length=300,
        null=True,
        blank=True,
        help_text=_("Label to be displayed in the user interface"),
    )
    description = models.CharField(
        _("description"), max_length=500, null=True, blank=True
    )
    type = models.CharField(
        _("type"),
        max_length=20,
        null=True,
        blank=True,
        choices=types,
        default="default",
    )
    mode_future = models.CharField(
        _("mode in future periods"),
        max_length=20,
        null=True,
        blank=True,
        choices=modes,
        default="edit",
    )
    mode_past = models.CharField(
        _("mode in past periods"),
        max_length=20,
        null=True,
        blank=True,
        choices=modes,
        default="edit",
    )
    compute_expression = models.CharField(
        _("compute expression"),
        max_length=300,
        null=True,
        blank=True,
        help_text=_("Formula to compute values"),
    )
    update_expression = models.CharField(
        _("update expression"),
        max_length=300,
        null=True,
        blank=True,
        help_text=_("Formula executed when updating this field"),
    )
    initially_hidden = models.BooleanField(
        _("initially hidden"),
        null=True,
        blank=True,
        help_text=_("controls whether or not this measure is visible by default"),
    )
    formatter = models.CharField(
        _("format"),
        max_length=20,
        null=True,
        blank=True,
        choices=formatters,
        default="number",
    )
    discrete = models.BooleanField(_("discrete"), null=True, blank=True)
    defaultvalue = models.DecimalField(
        _("default value"),
        max_digits=20,
        decimal_places=8,
        default=0,
        null=True,
        blank=True,
    )
    overrides = models.CharField(
        _("override measure"), max_length=300, null=True, blank=True
    )

    @property
    def editable(self):
        return self.mode_future == "edit" or self.mode_past == "edit"

    @property
    def verbose_name(self):
        return self.label or self.name

    @property
    def computed(self):
        """
        A measure can be computed, either in frontend javascript or in backend python.
        TODO Make this a database field rather than hidden logic.
        """
        return getattr(self, "_computed", False)

    @computed.setter
    def computed(self, value):
        self._computed = value

    def clean(self):
        if self.name and not self.name.isalnum():
            raise ValidationError(_("Name can only be alphanumeric"))

    class Meta(AuditModel.Meta):
        db_table = "measure"
        verbose_name = _("measure")
        verbose_name_plural = _("measures")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ForecastPlanView(models.Model):

    # Model managers
    objects = models.Manager()  # The default model manager

    # Database fields
    name = models.CharField(
        "name", max_length=300, null=False, blank=False, primary_key=True
    )
    item_id = models.CharField("item", max_length=300, null=False, blank=False)
    location_id = models.CharField("location", max_length=300, null=False, blank=False)
    customer_id = models.CharField("customer", max_length=300, null=False, blank=False)
    method = models.CharField("method", max_length=64, null=False, blank=False)
    out_method = models.CharField("out_method", max_length=64, null=False, blank=False)
    out_smape = models.DecimalField(
        "out_smape", null=True, blank=True, max_digits=20, decimal_places=8
    )

    class Meta(AuditModel.Meta):
        db_table = "forecastreport_view"
        verbose_name = "forecastreport_view"
        verbose_name_plural = "forecastreports_view"
        unique_together = (("item_id", "location_id", "customer_id"),)
        managed = False


def Benchmark():
    """
    Code used for testing the throughput of the forecast engine. It posts
    a continuous series of random forecast updates.

    To test, you will need to launch multiple Python processes executing this
    function because the forecast engine can handle more messages per second
    than a single test process can generate. The test script is the bottleneck.
    """
    session = requests.Session()
    items = [i.name for i in Item.objects.all().only("name")]
    customers = [i.name for i in Customer.objects.all().only("name")]
    locations = [i.name for i in Location.objects.all().only("name")]
    buckets = [
        (date(2019, 12, 2), date(2019, 12, 9)),
        (date(2019, 12, 9), date(2019, 12, 16)),
        (date(2019, 12, 16), date(2019, 12, 23)),
        (date(2019, 12, 23), date(2019, 12, 30)),
    ]
    print("items:", items)
    print("customers:", customers)
    print("locations:", locations)
    print("buckets:", buckets)

    count = 0
    start = datetime.now()
    while True:
        count += 1
        bckt = random.choice(buckets)
        Forecast.updatePlan(
            startdate=bckt[0],
            enddate=bckt[1],
            forecastoverride=random.randint(0, 1000),
            ordersadjustment=None,
            units=False,
            forecast=None,
            item=random.choice(items),
            location=random.choice(locations),
            customer=random.choice(customers),
            session=session,
        )
        if count % 1000 == 0:
            delta = datetime.now() - start
            print(
                count,
                " messages ",
                delta,
                round(count / delta.total_seconds()),
                "per second",
            )