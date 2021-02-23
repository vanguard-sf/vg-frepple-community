#
# Copyright (C) 2007-2013 by frePPLe bv
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from django.conf import settings
from django.db.models import F, DateTimeField, DurationField, FloatField
from django.db.models.functions import Cast
from django.db.models.expressions import RawSQL
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_text
from django.utils.text import format_lazy

from freppledb.boot import getAttributeFields
from freppledb.input.models import (
    Resource,
    Operation,
    Location,
    Item,
    OperationResource,
    OperationMaterial,
    Calendar,
    CalendarBucket,
    ManufacturingOrder,
    SubOperation,
    searchmode,
    OperationPlan,
)
from freppledb.common.report import (
    GridReport,
    GridFieldBool,
    GridFieldLastModified,
    GridFieldDateTime,
    GridFieldTime,
    GridFieldText,
    GridFieldHierarchicalText,
    GridFieldNumber,
    GridFieldInteger,
    GridFieldCurrency,
    GridFieldChoice,
    GridFieldDuration,
    GridFieldJSON,
)
from .utils import OperationPlanMixin

import logging

logger = logging.getLogger(__name__)


class OperationResourceList(GridReport):
    title = _("operation resources")
    basequeryset = OperationResource.objects.all()
    model = OperationResource
    frozenColumns = 1
    help_url = "modeling-wizard/manufacturing-capacity/operation-resources.html"

    rows = (
        GridFieldInteger(
            "id",
            title=_("identifier"),
            key=True,
            formatter="detail",
            extra='"role":"input/operationresource"',
            initially_hidden=True,
        ),
        GridFieldText(
            "operation",
            title=_("operation"),
            field_name="operation__name",
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldHierarchicalText(
            "resource",
            title=_("resource"),
            field_name="resource__name",
            formatter="detail",
            extra='"role":"input/resource"',
            model=Resource,
        ),
        GridFieldText(
            "skill",
            title=_("skill"),
            field_name="skill__name",
            formatter="detail",
            extra='"role":"input/skill"',
            initially_hidden=True,
        ),
        GridFieldNumber("quantity", title=_("quantity")),
        GridFieldNumber(
            "quantity_fixed", title=_("quantity fixed"), initially_hidden=True
        ),
        GridFieldDateTime(
            "effective_start", title=_("effective start"), initially_hidden=True
        ),
        GridFieldDateTime(
            "effective_end", title=_("effective end"), initially_hidden=True
        ),
        GridFieldText("name", title=_("name"), initially_hidden=True),
        GridFieldInteger("priority", title=_("priority"), initially_hidden=True),
        GridFieldText("setup", title=_("setup"), initially_hidden=True),
        GridFieldChoice(
            "search", title=_("search mode"), choices=searchmode, initially_hidden=True
        ),
        GridFieldText("source", title=_("source"), initially_hidden=True),
        GridFieldLastModified("lastmodified"),
        # Operation fields
        GridFieldText(
            "operation__description",
            title=format_lazy("{} - {}", _("operation"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__category",
            title=format_lazy("{} - {}", _("operation"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__subcategory",
            title=format_lazy("{} - {}", _("operation"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "operation__type",
            title=format_lazy("{} - {}", _("operation"), _("type")),
            choices=Operation.types,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__duration",
            title=format_lazy("{} - {}", _("operation"), _("duration")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__duration_per",
            title=format_lazy("{} - {}", _("operation"), _("duration per unit")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__fence",
            title=format_lazy("{} - {}", _("operation"), _("release fence")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__posttime",
            title=format_lazy("{} - {}", _("operation"), _("post-op time")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizeminimum",
            title=format_lazy("{} - {}", _("operation"), _("size minimum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizemultiple",
            title=format_lazy("{} - {}", _("operation"), _("size multiple")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizemaximum",
            title=format_lazy("{} - {}", _("operation"), _("size maximum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldInteger(
            "operation__priority",
            title=format_lazy("{} - {}", _("operation"), _("priority")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "operation__effective_start",
            title=format_lazy("{} - {}", _("operation"), _("effective start")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "operation__effective_end",
            title=format_lazy("{} - {}", _("operation"), _("effective end")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldCurrency(
            "operation__cost",
            title=format_lazy("{} - {}", _("operation"), _("cost")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "operation__search",
            title=format_lazy("{} - {}", _("operation"), _("search mode")),
            choices=searchmode,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__source",
            title=format_lazy("{} - {}", _("operation"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "operation__lastmodified",
            title=format_lazy("{} - {}", _("operation"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
        # Optional fields referencing the resource
        GridFieldText(
            "resource__description",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("description")),
        ),
        GridFieldText(
            "resource__category",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("category")),
        ),
        GridFieldText(
            "resource__subcategory",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("subcategory")),
        ),
        GridFieldText(
            "resource__type",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("type")),
        ),
        GridFieldNumber(
            "resource__maximum",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("maximum")),
        ),
        GridFieldText(
            "resource__maximum_calendar",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("maximum calendar")),
            field_name="resource__maximum_calendar__name",
            formatter="detail",
            extra='"role":"input/calendar"',
        ),
        GridFieldCurrency(
            "resource__cost",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("cost")),
        ),
        GridFieldDuration(
            "resource__maxearly",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("maxearly")),
        ),
        GridFieldText(
            "resource__setupmatrix",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("setupmatrix")),
            field_name="resource__setupmatrix__name",
            formatter="detail",
            extra='"role":"input/setupmatrix"',
        ),
        GridFieldText(
            "resource__setup",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("setup")),
        ),
        GridFieldText(
            "resource__location",
            editable=False,
            initially_hidden=True,
            title=format_lazy("{} - {}", _("resource"), _("location")),
            field_name="resource__location__name",
            formatter="detail",
            extra='"role":"input/location"',
        ),
    )


class OperationMaterialList(GridReport):
    title = _("operation materials")
    basequeryset = OperationMaterial.objects.all()
    model = OperationMaterial
    frozenColumns = 1
    help_url = "modeling-wizard/manufacturing-bom/operation-materials.html"

    rows = (
        GridFieldInteger(
            "id",
            title=_("identifier"),
            key=True,
            formatter="detail",
            extra='"role":"input/operationmaterial"',
            initially_hidden=True,
        ),
        GridFieldText(
            "operation",
            title=_("operation"),
            field_name="operation__name",
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldHierarchicalText(
            "item",
            title=_("item"),
            field_name="item__name",
            formatter="detail",
            extra='"role":"input/item"',
            model=Item,
        ),
        GridFieldChoice("type", title=_("type"), choices=OperationMaterial.types),
        GridFieldNumber("quantity", title=_("quantity")),
        GridFieldNumber(
            "quantity_fixed", title=_("fixed quantity"), initially_hidden=True
        ),
        GridFieldDateTime(
            "effective_start", title=_("effective start"), initially_hidden=True
        ),
        GridFieldDateTime(
            "effective_end", title=_("effective end"), initially_hidden=True
        ),
        GridFieldText("name", title=_("name"), initially_hidden=True),
        GridFieldInteger("priority", title=_("priority"), initially_hidden=True),
        GridFieldChoice(
            "search", title=_("search mode"), choices=searchmode, initially_hidden=True
        ),
        GridFieldText("source", title=_("source"), initially_hidden=True),
        GridFieldLastModified("lastmodified"),
        GridFieldNumber(
            "transferbatch", title=_("transfer batch quantity"), initially_hidden=True
        ),
        GridFieldDuration("offset", title=_("offset"), initially_hidden=True),
        # Operation fields
        GridFieldText(
            "operation__description",
            title=format_lazy("{} - {}", _("operation"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__category",
            title=format_lazy("{} - {}", _("operation"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__subcategory",
            title=format_lazy("{} - {}", _("operation"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "operation__type",
            title=format_lazy("{} - {}", _("operation"), _("type")),
            choices=Operation.types,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__duration",
            title=format_lazy("{} - {}", _("operation"), _("duration")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__duration_per",
            title=format_lazy("{} - {}", _("operation"), _("duration per unit")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__fence",
            title=format_lazy("{} - {}", _("operation"), _("release fence")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__posttime",
            title=format_lazy("{} - {}", _("operation"), _("post-op time")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizeminimum",
            title=format_lazy("{} - {}", _("operation"), _("size minimum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizemultiple",
            title=format_lazy("{} - {}", _("operation"), _("size multiple")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizemaximum",
            title=format_lazy("{} - {}", _("operation"), _("size maximum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldInteger(
            "operation__priority",
            title=format_lazy("{} - {}", _("operation"), _("priority")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "operation__effective_start",
            title=format_lazy("{} - {}", _("operation"), _("effective start")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "operation__effective_end",
            title=format_lazy("{} - {}", _("operation"), _("effective end")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldCurrency(
            "operation__cost",
            title=format_lazy("{} - {}", _("operation"), _("cost")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "operation__search",
            title=format_lazy("{} - {}", _("operation"), _("search mode")),
            choices=searchmode,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__source",
            title=format_lazy("{} - {}", _("operation"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "operation__lastmodified",
            title=format_lazy("{} - {}", _("operation"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
        # Optional fields referencing the item
        GridFieldText(
            "item__type",
            title=format_lazy("{} - {}", _("item"), _("type")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "item__description",
            title=format_lazy("{} - {}", _("item"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "item__category",
            title=format_lazy("{} - {}", _("item"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "item__subcategory",
            title=format_lazy("{} - {}", _("item"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "item__owner",
            title=format_lazy("{} - {}", _("item"), _("owner")),
            field_name="item__owner__name",
            initially_hidden=True,
            editable=False,
        ),
        GridFieldCurrency(
            "item__cost",
            title=format_lazy("{} - {}", _("item"), _("cost")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "item__volume",
            title=format_lazy("{} - {}", _("item"), _("volume")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "item__weight",
            title=format_lazy("{} - {}", _("item"), _("weight")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "item__source",
            title=format_lazy("{} - {}", _("item"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "item__lastmodified",
            title=format_lazy("{} - {}", _("item"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
    )


class CalendarList(GridReport):
    title = _("calendars")
    basequeryset = Calendar.objects.all()
    model = Calendar
    frozenColumns = 1
    help_url = "model-reference/calendars.html"

    rows = (
        GridFieldText(
            "name",
            title=_("name"),
            key=True,
            formatter="detail",
            extra='"role":"input/calendar"',
        ),
        GridFieldText("description", title=_("description")),
        GridFieldText("category", title=_("category"), initially_hidden=True),
        GridFieldText("subcategory", title=_("subcategory"), initially_hidden=True),
        GridFieldNumber("defaultvalue", title=_("default value")),
        GridFieldText("source", title=_("source"), initially_hidden=True),
        GridFieldLastModified("lastmodified"),
    )


class CalendarBucketList(GridReport):
    title = _("calendar buckets")
    basequeryset = CalendarBucket.objects.all()
    model = CalendarBucket
    frozenColumns = 1
    help_url = "model-reference/calendar-buckets.html"

    rows = (
        GridFieldInteger(
            "id",
            title=_("identifier"),
            formatter="detail",
            extra='"role":"input/calendarbucket"',
            initially_hidden=True,
        ),
        GridFieldText(
            "calendar",
            title=_("calendar"),
            field_name="calendar__name",
            formatter="detail",
            extra='"role":"input/calendar"',
        ),
        GridFieldDateTime("startdate", title=_("start date")),
        GridFieldDateTime("enddate", title=_("end date")),
        GridFieldNumber("value", title=_("value")),
        GridFieldInteger("priority", title=_("priority")),
        GridFieldBool("monday", title=_("Monday")),
        GridFieldBool("tuesday", title=_("Tuesday")),
        GridFieldBool("wednesday", title=_("Wednesday")),
        GridFieldBool("thursday", title=_("Thursday")),
        GridFieldBool("friday", title=_("Friday")),
        GridFieldBool("saturday", title=_("Saturday")),
        GridFieldBool("sunday", title=_("Sunday")),
        GridFieldTime("starttime", title=_("start time")),
        GridFieldTime("endtime", title=_("end time")),
        GridFieldText(
            "source", title=_("source"), initially_hidden=True
        ),  # Not really right, since the engine doesn't read or store it
        GridFieldLastModified("lastmodified"),
    )


class OperationList(GridReport):
    title = _("operations")
    basequeryset = Operation.objects.all()
    model = Operation
    frozenColumns = 1
    help_url = "modeling-wizard/manufacturing-bom/operations.html"

    rows = (
        GridFieldText(
            "name",
            title=_("name"),
            key=True,
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldText("description", title=_("description"), initially_hidden=True),
        GridFieldText("category", title=_("category"), initially_hidden=True),
        GridFieldText("subcategory", title=_("subcategory"), initially_hidden=True),
        GridFieldChoice("type", title=_("type"), choices=Operation.types),
        GridFieldHierarchicalText(
            "item",
            title=_("item"),
            field_name="item__name",
            formatter="detail",
            extra='"role":"input/item"',
            model=Item,
        ),
        GridFieldHierarchicalText(
            "location",
            title=_("location"),
            field_name="location__name",
            formatter="detail",
            extra='"role":"input/location"',
            model=Location,
        ),
        GridFieldDuration("duration", title=_("duration")),
        GridFieldDuration("duration_per", title=_("duration per unit")),
        GridFieldDuration("fence", title=_("release fence"), initially_hidden=True),
        GridFieldDuration("posttime", title=_("post-op time"), initially_hidden=True),
        GridFieldNumber("sizeminimum", title=_("size minimum"), initially_hidden=True),
        GridFieldNumber(
            "sizemultiple", title=_("size multiple"), initially_hidden=True
        ),
        GridFieldNumber("sizemaximum", title=_("size maximum"), initially_hidden=True),
        GridFieldText(
            "available",
            title=_("available"),
            field_name="available__name",
            formatter="detail",
            extra='"role":"input/calendar"',
            initially_hidden=True,
        ),
        GridFieldText(
            "owner",
            title=_("owner"),
            field_name="owner__name",
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldInteger("priority", title=_("priority"), initially_hidden=True),
        GridFieldDateTime(
            "effective_start", title=_("effective start"), initially_hidden=True
        ),
        GridFieldDateTime(
            "effective_end", title=_("effective end"), initially_hidden=True
        ),
        GridFieldCurrency("cost", title=_("cost"), initially_hidden=True),
        GridFieldChoice(
            "search", title=_("search mode"), choices=searchmode, initially_hidden=True
        ),
        GridFieldText("source", title=_("source"), initially_hidden=True),
        GridFieldLastModified("lastmodified"),
    )


class SubOperationList(GridReport):
    title = _("suboperations")
    basequeryset = SubOperation.objects.all()
    model = SubOperation
    frozenColumns = 1
    help_url = "model-reference/suboperations.html"

    rows = (
        GridFieldInteger("id", title=_("identifier"), key=True, initially_hidden=True),
        GridFieldText(
            "operation",
            title=_("operation"),
            field_name="operation__name",
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldText(
            "suboperation",
            title=_("suboperation"),
            field_name="suboperation__name",
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldInteger("priority", title=_("priority")),
        GridFieldDateTime(
            "effective_start", title=_("effective start"), initially_hidden=True
        ),
        GridFieldDateTime(
            "effective_end", title=_("effective end"), initially_hidden=True
        ),
        GridFieldText("source", title=_("source"), initially_hidden=True),
        GridFieldLastModified("lastmodified"),
        # Operation fields
        GridFieldText(
            "operation__description",
            title=format_lazy("{} - {}", _("operation"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__category",
            title=format_lazy("{} - {}", _("operation"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__subcategory",
            title=format_lazy("{} - {}", _("operation"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "operation__type",
            title=format_lazy("{} - {}", _("operation"), _("type")),
            choices=Operation.types,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__duration",
            title=format_lazy("{} - {}", _("operation"), _("duration")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__duration_per",
            title=format_lazy("{} - {}", _("operation"), _("duration per unit")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__fence",
            title=format_lazy("{} - {}", _("operation"), _("release fence")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "operation__posttime",
            title=format_lazy("{} - {}", _("operation"), _("post-op time")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizeminimum",
            title=format_lazy("{} - {}", _("operation"), _("size minimum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizemultiple",
            title=format_lazy("{} - {}", _("operation"), _("size multiple")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "operation__sizemaximum",
            title=format_lazy("{} - {}", _("operation"), _("size maximum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldInteger(
            "operation__priority",
            title=format_lazy("{} - {}", _("operation"), _("priority")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "operation__effective_start",
            title=format_lazy("{} - {}", _("operation"), _("effective start")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "operation__effective_end",
            title=format_lazy("{} - {}", _("operation"), _("effective end")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldCurrency(
            "operation__cost",
            title=format_lazy("{} - {}", _("operation"), _("cost")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "operation__search",
            title=format_lazy("{} - {}", _("operation"), _("search mode")),
            choices=searchmode,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__source",
            title=format_lazy("{} - {}", _("operation"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "operation__lastmodified",
            title=format_lazy("{} - {}", _("operation"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
        # Suboperation fields
        GridFieldText(
            "suboperation__description",
            title=format_lazy("{} - {}", _("suboperation"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "suboperation__category",
            title=format_lazy("{} - {}", _("suboperation"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "suboperation__subcategory",
            title=format_lazy("{} - {}", _("suboperation"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "suboperation__type",
            title=format_lazy("{} - {}", _("suboperation"), _("type")),
            choices=Operation.types,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "suboperation__duration",
            title=format_lazy("{} - {}", _("suboperation"), _("duration")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "suboperation__duration_per",
            title=format_lazy("{} - {}", _("suboperation"), _("duration per unit")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "suboperation__fence",
            title=format_lazy("{} - {}", _("suboperation"), _("release fence")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDuration(
            "suboperation__posttime",
            title=format_lazy("{} - {}", _("suboperation"), _("post-op time")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "suboperation__sizeminimum",
            title=format_lazy("{} - {}", _("suboperation"), _("size minimum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "suboperation__sizemultiple",
            title=format_lazy("{} - {}", _("suboperation"), _("size multiple")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "suboperation__sizemaximum",
            title=format_lazy("{} - {}", _("suboperation"), _("size maximum")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldInteger(
            "suboperation__priority",
            title=format_lazy("{} - {}", _("suboperation"), _("priority")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "suboperation__effective_start",
            title=format_lazy("{} - {}", _("suboperation"), _("effective start")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldDateTime(
            "suboperation__effective_end",
            title=format_lazy("{} - {}", _("suboperation"), _("effective end")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldCurrency(
            "suboperation__cost",
            title=format_lazy("{} - {}", _("suboperation"), _("cost")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldChoice(
            "suboperation__search",
            title=format_lazy("{} - {}", _("suboperation"), _("search mode")),
            choices=searchmode,
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "suboperation__source",
            title=format_lazy("{} - {}", _("suboperation"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "suboperation__lastmodified",
            title=format_lazy("{} - {}", _("suboperation"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
    )


class ManufacturingOrderList(OperationPlanMixin, GridReport):
    template = "input/operationplanreport.html"
    title = _("manufacturing orders")
    default_sort = (1, "desc")
    model = ManufacturingOrder
    frozenColumns = 1
    multiselect = True
    editable = True
    height = 250
    help_url = "modeling-wizard/manufacturing-bom/manufacturing-orders.html"

    @classmethod
    def extra_context(reportclass, request, *args, **kwargs):
        if args and args[0]:
            request.session["lasttab"] = "plandetail"
            paths = request.path.split("/")
            path = paths[4]
            if path == "location" or request.path.startswith("/detail/input/location/"):
                return {
                    "active_tab": "plandetail",
                    "model": Location,
                    "title": force_text(Location._meta.verbose_name) + " " + args[0],
                    "post_title": _("manufacturing orders"),
                }
            elif path == "operation" or request.path.startswith(
                "/detail/input/operation/"
            ):
                return {
                    "active_tab": "plandetail",
                    "model": Operation,
                    "title": force_text(Operation._meta.verbose_name) + " " + args[0],
                    "post_title": _("manufacturing orders"),
                }
            elif path == "item" or request.path.startswith("/detail/input/item/"):
                return {
                    "active_tab": "plandetail",
                    "model": Item,
                    "title": force_text(Item._meta.verbose_name) + " " + args[0],
                    "post_title": _("manufacturing orders"),
                }
            elif path == "operationplanmaterial":
                return {
                    "active_tab": "plandetail",
                    "model": Item,
                    "title": force_text(Item._meta.verbose_name) + " " + args[0],
                    "post_title": force_text(
                        _("work in progress in %(loc)s at %(date)s")
                        % {"loc": args[1], "date": args[2]}
                    ),
                }
            elif path == "produced":
                return {
                    "active_tab": "plandetail",
                    "model": Item,
                    "title": force_text(Item._meta.verbose_name) + " " + args[0],
                    "post_title": force_text(
                        _("produced in %(loc)s between %(date1)s and %(date2)s")
                        % {"loc": args[1], "date1": args[2], "date2": args[3]}
                    ),
                }
            elif path == "consumed":
                return {
                    "active_tab": "plandetail",
                    "model": Item,
                    "title": force_text(Item._meta.verbose_name) + " " + args[0],
                    "post_title": force_text(
                        _("consumed in %(loc)s between %(date1)s and %(date2)s")
                        % {"loc": args[1], "date1": args[2], "date2": args[3]}
                    ),
                }
            else:
                return {"active_tab": "edit", "model": Item}
        elif "parentreference" in request.GET:
            return {
                "active_tab": "plandetail",
                "title": force_text(ManufacturingOrder._meta.verbose_name)
                + " "
                + request.GET["parentreference"],
            }
        else:
            return {"active_tab": "plandetail"}

    @classmethod
    def basequeryset(reportclass, request, *args, **kwargs):
        q = ManufacturingOrder.objects.all()
        if args and args[0]:
            path = request.path.split("/")[4]
            if path == "location" or request.path.startswith("/detail/input/location/"):
                q = q.filter(location=args[0])
            elif path == "operation" or request.path.startswith(
                "/detail/input/operation/"
            ):
                q = q.filter(operation=args[0])
            elif path == "item" or request.path.startswith("/detail/input/item/"):
                q = q.filter(
                    reference__in=RawSQL(
                        """
          select operationplan_id from operationplan
          inner join operationplanmaterial on operationplanmaterial.operationplan_id = operationplan.reference
          and operationplanmaterial.item_id = %s
          and operationplanmaterial.quantity > 0
          where operationplan.type = 'MO'
          """,
                        (args[0],),
                    )
                )
            elif path == "operationplanmaterial":
                q = q.filter(
                    reference__in=RawSQL(
                        """
          select operationplan_id from operationplan
          inner join operationplanmaterial on operationplanmaterial.operationplan_id = operationplan.reference
          and operationplanmaterial.item_id = %s and operationplanmaterial.location_id = %s
          and operationplan.startdate < %s and operationplan.enddate >= %s
          where operationplan.type = 'MO'
          """,
                        (args[0], args[1], args[2], args[2]),
                    )
                )
            elif path == "produced":
                q = q.filter(
                    reference__in=RawSQL(
                        """
          select operationplan_id from operationplan
          inner join operationplanmaterial on operationplanmaterial.operationplan_id = operationplan.reference
          and operationplanmaterial.item_id = %s and operationplanmaterial.location_id = %s
          and operationplanmaterial.flowdate >= %s and operationplanmaterial.flowdate < %s
          and operationplanmaterial.quantity > 0
          where operationplan.type = 'MO'
          """,
                        (args[0], args[1], args[2], args[3]),
                    )
                )
            elif path == "consumed":
                q = q.filter(
                    reference__in=RawSQL(
                        """
          select operationplan_id from operationplan
          inner join operationplanmaterial on operationplanmaterial.operationplan_id = operationplan.reference
          and operationplanmaterial.item_id = %s and operationplanmaterial.location_id = %s
          and operationplanmaterial.flowdate >= %s and operationplanmaterial.flowdate < %s
          and operationplanmaterial.quantity < 0
          where operationplan.type = 'MO'
          """,
                        (args[0], args[1], args[2], args[3]),
                    )
                )

        q = reportclass.operationplanExtraBasequery(q, request)
        return q.annotate(
            material=RawSQL(
                "(select json_agg(json_build_array(item_id, quantity)) from (select item_id, round(quantity,2) quantity from operationplanmaterial where operationplan.reference = operationplanmaterial.operationplan_id  order by quantity limit 10) mat)",
                [],
            ),
            resource=RawSQL(
                "(select json_agg(json_build_array(resource_id, quantity)) from (select resource_id, round(quantity,2) quantity from operationplanresource where operationplan.reference = operationplanresource.operationplan_id  order by quantity desc limit 10) res)",
                [],
            ),
            setup=RawSQL(
                "(select json_agg(json_build_array(resource_id, setup)) from (select resource_id, setup from operationplanresource where setup is not null and operationplan.reference = operationplanresource.operationplan_id order by resource_id limit 10) res)",
                [],
            ),
            setup_duration=Cast(
                RawSQL(
                    "(operationplan.plan->>'setup')::numeric * '1 second'::interval", []
                ),
                DurationField(),
            ),
            setup_end=Cast(
                RawSQL("(operationplan.plan->>'setupend')", []), DateTimeField()
            ),
            feasible=RawSQL(
                "coalesce((operationplan.plan->>'feasible')::boolean, true)", []
            ),
            opplan_duration=RawSQL(
                "(operationplan.enddate - operationplan.startdate)", []
            ),
            opplan_net_duration=RawSQL(
                "(operationplan.enddate - operationplan.startdate - coalesce((operationplan.plan->>'unavailable')::int * interval '1 second', interval '0 second'))",
                [],
            ),
            inventory_item=RawSQL("operationplan.plan->'item'", []),
            inventory_location=RawSQL("operationplan.plan->'location'", []),
            computed_color=RawSQL(
                """
                case when operationplan.color >= 999999 and operationplan.plan ? 'item' then
                999999
                - extract(epoch from operationplan.delay)/86400.0
                + 1000000
                when operationplan.color >= 999999 and not(operationplan.plan ? 'item') then
                999999
                - extract(epoch from operationplan.delay)/86400.0
                else operationplan.color
                end
                """,
                [],
            ),
            total_cost=Cast(
                F("operation__cost") * F("quantity"), output_field=FloatField()
            ),
            total_volume=Cast(
                F("item__volume") * F("quantity"), output_field=FloatField()
            ),
            total_weight=Cast(
                F("item__weight") * F("quantity"), output_field=FloatField()
            ),
        )

    rows = (
        GridFieldText(
            "reference",
            title=_("reference"),
            key=True,
            formatter="detail",
            extra="role:'input/manufacturingorder'",
            editable=not settings.ERP_CONNECTOR,
        ),
        GridFieldText(
            "batch", title=_("batch"), editable="true", initially_hidden=True
        ),
        GridFieldNumber(
            "computed_color",
            title=_("inventory status"),
            formatter="color",
            width="125",
            editable=False,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"min"',
        ),
        GridFieldNumber("color", hidden=True),
        GridFieldHierarchicalText(
            "item__name",
            title=_("item"),
            formatter="detail",
            extra='"role":"input/item"',
            editable=False,
            model=Item,
        ),
        GridFieldHierarchicalText(
            "operation__location__name",
            title=_("location"),
            formatter="detail",
            extra='"role":"input/location"',
            editable=False,
            model=Location,
        ),
        GridFieldText(
            "operation",
            title=_("operation"),
            field_name="operation__name",
            formatter="detail",
            extra='"role":"input/operation"',
        ),
        GridFieldDateTime(
            "startdate",
            title=_("start date"),
            extra='"formatoptions":{"srcformat":"Y-m-d H:i:s","newformat":"Y-m-d H:i:s", "defaultValue":""}, "summaryType":"min"',
        ),
        GridFieldDateTime(
            "enddate",
            title=_("end date"),
            extra='"formatoptions":{"srcformat":"Y-m-d H:i:s","newformat":"Y-m-d H:i:s", "defaultValue":""}, "summaryType":"max"',
        ),
        GridFieldDuration(
            "opplan_duration",
            title=_("duration"),
            formatter="duration",
            editable=False,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"',
        ),
        GridFieldDuration(
            "opplan_net_duration",
            title=_("net duration"),
            formatter="duration",
            editable=False,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"',
        ),
        GridFieldNumber(
            "quantity",
            title=_("quantity"),
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"',
        ),
        GridFieldCurrency(
            "total_cost",
            title=_("total cost"),
            editable=False,
            search=False,
            initially_hidden=True,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"',
        ),
        GridFieldNumber(
            "total_volume",
            title=_("total volume"),
            editable=False,
            search=False,
            initially_hidden=True,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"',
        ),
        GridFieldNumber(
            "total_weight",
            title=_("total weight"),
            editable=False,
            search=False,
            initially_hidden=True,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"',
        ),
        GridFieldChoice(
            "status",
            title=_("status"),
            choices=OperationPlan.orderstatus,
            editable=not settings.ERP_CONNECTOR,
        ),
        GridFieldNumber(
            "criticality",
            title=_("criticality"),
            editable=False,
            initially_hidden=True,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"min"',
        ),
        GridFieldDuration(
            "delay",
            title=_("delay"),
            editable=False,
            initially_hidden=True,
            extra='"formatoptions":{"defaultValue":""}, "summaryType":"max"',
        ),
        GridFieldJSON(
            "demands",
            title=_("demands"),
            editable=False,
            search=True,
            sortable=False,
            formatter="demanddetail",
            extra='"role":"input/demand"',
        ),
        GridFieldJSON(
            "material",
            title=_("materials"),
            editable=False,
            search=True,
            sortable=False,
            initially_hidden=True,
            formatter="listdetail",
            extra='"role":"input/item"',
        ),
        GridFieldJSON(
            "resource",
            title=_("resources"),
            editable=False,
            search=True,
            sortable=False,
            initially_hidden=True,
            formatter="listdetail",
            extra='"role":"input/resource"',
        ),
        GridFieldText(
            "setup",
            title=_("setups"),
            editable=False,
            search=True,
            sortable=False,
            initially_hidden=True,
            formatter="listdetail",
            extra='"role":"input/resource"',
        ),
        GridFieldText(
            "owner",
            title=_("owner"),
            field_name="owner__reference",
            formatter="detail",
            extra="role:'input/manufacturingorder'",
            initially_hidden=True,
        ),
        GridFieldText("source", title=_("source"), initially_hidden=True),
        GridFieldLastModified("lastmodified"),
        GridFieldText(
            "operation__description",
            title=format_lazy("{} - {}", _("operation"), _("description")),
            initially_hidden=True,
        ),
        GridFieldText(
            "operation__category",
            title=format_lazy("{} - {}", _("operation"), _("category")),
            initially_hidden=True,
        ),
        GridFieldText(
            "operation__subcategory",
            title=format_lazy("{} - {}", _("operation"), _("subcategory")),
            initially_hidden=True,
        ),
        GridFieldChoice(
            "operation__type",
            title=format_lazy("{} - {}", _("operation"), _("type")),
            choices=Operation.types,
            initially_hidden=True,
        ),
        GridFieldDuration(
            "operation__duration",
            title=format_lazy("{} - {}", _("operation"), _("duration")),
            initially_hidden=True,
        ),
        GridFieldDuration(
            "operation__duration_per",
            title=format_lazy("{} - {}", _("operation"), _("duration per unit")),
            initially_hidden=True,
        ),
        GridFieldDuration(
            "operation__fence",
            title=format_lazy("{} - {}", _("operation"), _("release fence")),
            initially_hidden=True,
        ),
        GridFieldDuration(
            "operation__posttime",
            title=format_lazy("{} - {}", _("operation"), _("post-op time")),
            initially_hidden=True,
        ),
        GridFieldNumber(
            "operation__sizeminimum",
            title=format_lazy("{} - {}", _("operation"), _("size minimum")),
            initially_hidden=True,
        ),
        GridFieldNumber(
            "operation__sizemultiple",
            title=format_lazy("{} - {}", _("operation"), _("size multiple")),
            initially_hidden=True,
        ),
        GridFieldNumber(
            "operation__sizemaximum",
            title=format_lazy("{} - {}", _("operation"), _("size maximum")),
            initially_hidden=True,
        ),
        GridFieldInteger(
            "operation__priority",
            title=format_lazy("{} - {}", _("operation"), _("priority")),
            initially_hidden=True,
        ),
        GridFieldDateTime(
            "operation__effective_start",
            title=format_lazy("{} - {}", _("operation"), _("effective start")),
            initially_hidden=True,
        ),
        GridFieldDateTime(
            "operation__effective_end",
            title=format_lazy("{} - {}", _("operation"), _("effective end")),
            initially_hidden=True,
        ),
        GridFieldCurrency(
            "operation__cost",
            title=format_lazy("{} - {}", _("operation"), _("cost")),
            initially_hidden=True,
        ),
        GridFieldChoice(
            "operation__search",
            title=format_lazy("{} - {}", _("operation"), _("search mode")),
            choices=searchmode,
            initially_hidden=True,
        ),
        GridFieldText(
            "operation__source",
            title=format_lazy("{} - {}", _("operation"), _("source")),
            initially_hidden=True,
        ),
        GridFieldLastModified(
            "operation__lastmodified",
            title=format_lazy("{} - {}", _("operation"), _("last modified")),
            initially_hidden=True,
        ),
        GridFieldDuration(
            "setup_duration",
            title=_("setup time"),
            initially_hidden=True,
            search=False,
            editable=False,
        ),
        GridFieldDateTime(
            "setup_end",
            title=_("setup end date"),
            initially_hidden=True,
            search=True,
            editable=False,
        ),
        GridFieldBool(
            "feasible",
            title=_("feasible"),
            editable=False,
            initially_hidden=True,
            search=True,
        ),
        # Optional fields referencing the item
        GridFieldText(
            "operation__item__type",
            title=format_lazy("{} - {}", _("item"), _("type")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__item__description",
            title=format_lazy("{} - {}", _("item"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__item__category",
            title=format_lazy("{} - {}", _("item"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__item__subcategory",
            title=format_lazy("{} - {}", _("item"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldCurrency(
            "item__cost",
            title=format_lazy("{} - {}", _("item"), _("cost")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "item__volume",
            title=format_lazy("{} - {}", _("item"), _("volume")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldNumber(
            "item__weight",
            title=format_lazy("{} - {}", _("item"), _("weight")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__item__owner",
            title=format_lazy("{} - {}", _("item"), _("owner")),
            field_name="operation__item__owner__name",
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__item__source",
            title=format_lazy("{} - {}", _("item"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "operation__item__lastmodified",
            title=format_lazy("{} - {}", _("item"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
        # Optional fields referencing the location
        GridFieldText(
            "operation__location__description",
            title=format_lazy("{} - {}", _("location"), _("description")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__location__category",
            title=format_lazy("{} - {}", _("location"), _("category")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__location__subcategory",
            title=format_lazy("{} - {}", _("location"), _("subcategory")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "operation__location__available",
            title=format_lazy("{} - {}", _("location"), _("available")),
            initially_hidden=True,
            field_name="operation__location__available__name",
            formatter="detail",
            extra='"role":"input/calendar"',
            editable=False,
        ),
        GridFieldText(
            "operation__location__owner",
            title=format_lazy("{} - {}", _("location"), _("owner")),
            initially_hidden=True,
            field_name="operation__location__owner__name",
            formatter="detail",
            extra='"role":"input/location"',
            editable=False,
        ),
        GridFieldText(
            "operation__location__source",
            title=format_lazy("{} - {}", _("location"), _("source")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldLastModified(
            "operation__location__lastmodified",
            title=format_lazy("{} - {}", _("location"), _("last modified")),
            initially_hidden=True,
            editable=False,
        ),
        GridFieldText(
            "end_items",
            title=_("end items"),
            editable=False,
            search=True,
            sortable=False,
            initially_hidden=True,
            formatter="listdetail",
            extra='"role":"input/item"',
        ),
    )

    if settings.ERP_CONNECTOR:
        actions = [
            {
                "name": "erp_incr_export",
                "label": format_lazy("export to {erp}", erp=settings.ERP_CONNECTOR),
                "function": "ERPconnection.IncrementalExport(jQuery('#grid'),'MO')",
            }
        ]
    else:
        actions = [
            {
                "name": "proposed",
                "label": format_lazy(
                    _("change status to {status}"), status=_("proposed")
                ),
                "function": "grid.setStatus('proposed')",
            },
            {
                "name": "approved",
                "label": format_lazy(
                    _("change status to {status}"), status=_("approved")
                ),
                "function": "grid.setStatus('approved')",
            },
            {
                "name": "confirmed",
                "label": format_lazy(
                    _("change status to {status}"), status=_("confirmed")
                ),
                "function": "grid.setStatus('confirmed')",
            },
            {
                "name": "completed",
                "label": format_lazy(
                    _("change status to {status}"), status=_("completed")
                ),
                "function": "grid.setStatus('completed')",
            },
            {
                "name": "closed",
                "label": format_lazy(
                    _("change status to {status}"), status=_("closed")
                ),
                "function": "grid.setStatus('closed')",
            },
        ]

    @classmethod
    def initialize(reportclass, request):
        if reportclass._attributes_added != 2:
            reportclass._attributes_added = 2
            for f in getAttributeFields(ManufacturingOrder):
                reportclass.rows += (f,)
            for f in getAttributeFields(Operation, related_name_prefix="operation"):
                f.editable = False
                reportclass.rows += (f,)
            for f in getAttributeFields(Item, related_name_prefix="item"):
                f.editable = False
                reportclass.rows += (f,)
            for f in getAttributeFields(Location, related_name_prefix="location"):
                f.editable = False
                reportclass.rows += (f,)