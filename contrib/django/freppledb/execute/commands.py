from __future__ import print_function
import os
import sys
from datetime import datetime

from django.db import transaction, DEFAULT_DB_ALIAS
from django.conf import settings

from freppledb.common.models import Parameter
from freppledb.execute.models import Task

import frepple


def printWelcome(prefix='frepple', database=DEFAULT_DB_ALIAS):
  # Send the output to a logfile
  if database == DEFAULT_DB_ALIAS:
    frepple.settings.logfile = os.path.join(settings.FREPPLE_LOGDIR, '%s.log' % prefix)
  else:
    frepple.settings.logfile = os.path.join(settings.FREPPLE_LOGDIR, '%s_%s.log' % (prefix, database))

  # Welcome message
  if settings.DATABASES[database]['ENGINE'] == 'django.db.backends.sqlite3':
    print("FrePPLe with processid %s on %s using sqlite3 database '%s'" % (
      os.getpid(),
      sys.platform,
      settings.DATABASES[database].get('NAME', '')
      ))
  else:
    print("FrePPLe with processid %s on %s using %s database '%s' as '%s' on '%s:%s'" % (
      os.getpid(),
      sys.platform,
      settings.DATABASES[database].get('ENGINE', '').split('.')[-1],
      settings.DATABASES[database].get('NAME', ''),
      settings.DATABASES[database].get('USER', ''),
      settings.DATABASES[database].get('HOST', ''),
      settings.DATABASES[database].get('PORT', '')
      ))


task = None


def logProgress(val, database=DEFAULT_DB_ALIAS):
  global task
  transaction.enter_transaction_management(using=database)
  try:
    if not task and 'FREPPLE_TASKID' in os.environ:
      try:
        task = Task.objects.all().using(database).get(pk=os.environ['FREPPLE_TASKID'])
      except:
        raise Exception("Task identifier not found")
    if task:
      if task.status == 'Canceling':
        task.status = 'Cancelled'
        task.save(using=database)
        sys.exit(2)
      else:
        task.status = '%d%%' % val
        task.save(using=database)
  finally:
    transaction.commit(using=database)
    transaction.leave_transaction_management(using=database)


def logMessage(msg, database=DEFAULT_DB_ALIAS):
  global task
  if task:
    transaction.enter_transaction_management(managed=False, using=database)
    transaction.managed(False, using=database)
    try:
      task.message = msg
      task.save(using=database)
    finally:
      transaction.commit(using=database)
      transaction.leave_transaction_management(using=database)


def createPlan(database=DEFAULT_DB_ALIAS):
  # Auxiliary functions for debugging
  def debugResource(res, mode):
    # if res.name != 'my favorite resource': return
    print("=> Situation on resource", res.name)
    for j in res.loadplans:
      print("=>  ", j.quantity, j.onhand, j.startdate, j.enddate, j.operation.name, j.operationplan.quantity, j.setup)

  def debugDemand(dem, mode):
    if dem.name == 'my favorite demand':
      print("=> Starting to plan demand ", dem.name)
      solver.loglevel = 2
    else:
      solver.loglevel = 0

  # Create a solver where the plan type are defined by an environment variable
  try:
    plantype = int(os.environ['FREPPLE_PLANTYPE'])
  except:
    plantype = 1  # Default is a constrained plan
  try:
    constraint = int(os.environ['FREPPLE_CONSTRAINT'])
  except:
    constraint = 15  # Default is with all constraints enabled
  solver = frepple.solver_mrp(
    name="MRP",
    constraints=constraint,
    plantype=plantype,
    loglevel=int(Parameter.getValue('plan.loglevel', database, 0)),
    lazydelay=int(Parameter.getValue('lazydelay', database, '86400')),
    allowsplits=(Parameter.getValue('allowsplits', database, 'true') == "true"),
    rotateresources=(Parameter.getValue('plan.rotateResources', database, 'true') == "true"),
    plansafetystockfirst=(Parameter.getValue('plan.planSafetyStockFirst', database, 'false') == "false"),
    iterationmax=int(Parameter.getValue('plan.iterationmax', database, '0'))
    #userexit_resource=debugResource,
    #userexit_demand=debugDemand
    )
  print("Plan type: ", plantype)
  print("Constraints: ", constraint)
  solver.solve()


def exportPlan(database=DEFAULT_DB_ALIAS):
  if settings.DATABASES[database]['ENGINE'] == 'django.db.backends.postgresql_psycopg2':
    from freppledb.execute.export_database_plan_postgresql import exportfrepple as export_plan_to_database
  else:
    from freppledb.execute.export_database_plan import exportfrepple as export_plan_to_database
  export_plan_to_database()


if __name__ == "__main__":
  # Select database
  try:
    db = os.environ['FREPPLE_DATABASE'] or DEFAULT_DB_ALIAS
  except:
    db = DEFAULT_DB_ALIAS

  # Use the test database if we are running the test suite
  if 'FREPPLE_TEST' in os.environ:
    settings.DATABASES[db]['NAME'] = settings.DATABASES[db]['TEST_NAME']
    if 'TEST_CHARSET' in os.environ:
      settings.DATABASES[db]['CHARSET'] = settings.DATABASES[db]['TEST_CHARSET']
    if 'TEST_COLLATION' in os.environ:
      settings.DATABASES[db]['COLLATION'] = settings.DATABASES[db]['TEST_COLLATION']
    if 'TEST_USER' in os.environ:
      settings.DATABASES[db]['USER'] = settings.DATABASES[db]['TEST_USER']

  printWelcome(database=db)
  logProgress(1, db)
  frepple.printsize()
  print("\nStart loading data from the database at", datetime.now().strftime("%H:%M:%S"))
  from freppledb.execute.load import loadData
  loadData(database=db, filter=None).run()
  frepple.printsize()
  logProgress(33, db)
  print("\nStart plan generation at", datetime.now().strftime("%H:%M:%S"))
  createPlan(db)
  frepple.printsize()
  logProgress(66, db)

  #print("\nStart exporting static model to the database at", datetime.now().strftime("%H:%M:%S"))
  #from freppledb.execute.export_database_static import exportStaticModel
  #exportStaticModel(database=db, source=None).run()

  print("\nStart exporting plan to the database at", datetime.now().strftime("%H:%M:%S"))
  exportPlan(db)

  #print("\nStart saving the plan to flat files at", datetime.now().strftime("%H:%M:%S"))
  #from freppledb.execute.export_file_plan import exportfrepple as export_plan_to_file
  #export_plan_to_file()

  #print("\nStart saving the plan to an XML file at", datetime.now().strftime("%H:%M:%S"))
  #frepple.saveXMLfile("output.1.xml","PLANDETAIL")
  #frepple.saveXMLfile("output.2.xml","PLAN")
  #frepple.saveXMLfile("output.3.xml","STANDARD")

  #print("Start deleting model data at", datetime.now().strftime("%H:%M:%S"))
  #frepple.erase(True)
  #frepple.printsize()

  print("\nFinished planning at", datetime.now().strftime("%H:%M:%S"))
  logProgress(100, db)
