/***************************************************************************
 *                                                                         *
 * Copyright (C) 2007-2013 by Johan De Taeye, frePPLe bvba                 *
 *                                                                         *
 * This library is free software; you can redistribute it and/or modify it *
 * under the terms of the GNU Affero General Public License as published   *
 * by the Free Software Foundation; either version 3 of the License, or    *
 * (at your option) any later version.                                     *
 *                                                                         *
 * This library is distributed in the hope that it will be useful,         *
 * but WITHOUT ANY WARRANTY; without even the implied warranty of          *
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the            *
 * GNU Affero General Public License for more details.                     *
 *                                                                         *
 * You should have received a copy of the GNU Affero General Public        *
 * License along with this program.                                        *
 * If not, see <http://www.gnu.org/licenses/>.                             *
 *                                                                         *
 ***************************************************************************/

#define FREPPLE_CORE
#include "frepple/solver.h"
namespace frepple
{

DECLARE_EXPORT const MetaClass* SolverMRP::metadata;
const Keyword tag_iterationthreshold("iterationthreshold");
const Keyword tag_iterationaccuracy("iterationaccuracy");
const Keyword tag_lazydelay("lazydelay");
const Keyword tag_allowsplits("allowsplits");
const Keyword SolverMRP::tag_rotateresources("rotateresources");
const Keyword tag_planSafetyStockFirst("plansafetystockfirst");
const Keyword tag_iterationmax("iterationmax");


void LibrarySolver::initialize()
{
  // Initialize only once
  static bool init = false;
  if (init)
  {
    logger << "Warning: Calling frepple::LibrarySolver::initialize() more "
        << "than once." << endl;
    return;
  }
  init = true;

  // Register all classes.
  int nok = 0;
  nok += SolverMRP::initialize();
  nok += OperatorDelete::initialize();
  if (nok) throw RuntimeException("Error registering new Python types");
}


int SolverMRP::initialize()
{
  // Initialize the metadata
  metadata = new MetaClass
  ("solver","solver_mrp",Object::createString<SolverMRP>,true);

  // Initialize the Python class
  FreppleClass<SolverMRP,Solver>::getType().addMethod("solve", solve, METH_VARARGS, "run the solver");
  FreppleClass<SolverMRP,Solver>::getType().addMethod("commit", commit, METH_NOARGS, "commit the plan changes");
  FreppleClass<SolverMRP,Solver>::getType().addMethod("rollback", rollback, METH_NOARGS, "rollback the plan changes");
  return FreppleClass<SolverMRP,Solver>::initialize();
}


DECLARE_EXPORT bool SolverMRP::demand_comparison(const Demand* l1, const Demand* l2)
{
  if (l1->getPriority() != l2->getPriority())
    return l1->getPriority() < l2->getPriority();
  else if (l1->getDue() != l2->getDue())
    return l1->getDue() < l2->getDue();
  else
    return l1->getQuantity() < l2->getQuantity();
}


DECLARE_EXPORT void SolverMRP::SolverMRPdata::commit()
{
  // Check
  SolverMRP* solver = getSolver();
  if (!demands || !solver)
    throw LogicException("Missing demands or solver.");

  // Message
  if (solver->getLogLevel()>0)
    logger << "Start solving cluster " << cluster << " at " << Date::now() << endl;

  // Solve the planning problem
  try
  {
    // TODO Propagate & solve initial shortages and overloads

    // Sort the demands of this problem.
    // We use a stable sort to get reproducible results between platforms
    // and STL implementations.
    stable_sort(demands->begin(), demands->end(), demand_comparison);

    // Solve for safety stock in buffers.
    if (solver->getPlanSafetyStockFirst())
    {
      constrainedPlanning = (solver->getPlanType() == 1);
      solveSafetyStock(solver);
    }

    // Loop through the list of all demands in this planning problem
    safety_stock_planning = false;
    constrainedPlanning = (solver->getPlanType() == 1);
    for (deque<Demand*>::const_iterator i = demands->begin();
        i != demands->end(); ++i)
    {
      iteration_count = 0;
      try
      {
        // Plan the demand
        (*i)->solve(*solver, this);
      }
      catch (...)
      {
        // Error message
        logger << "Error: Caught an exception while solving demand '"
            << (*i)->getName() << "':" << endl;
        try {throw;}
        catch (const bad_exception&) {logger << "  bad exception" << endl;}
        catch (const exception& e) {logger << "  " << e.what() << endl;}
        catch (...) {logger << "  Unknown type" << endl;}
      }
    }

    // Clean the list of demands of this cluster
    demands->clear();

    // Solve for safety stock in buffers.
    if (!solver->getPlanSafetyStockFirst()) solveSafetyStock(solver);
  }
  catch (...)
  {
    // We come in this exception handling code only if there is a problem with
    // with this cluster that goes beyond problems with single orders.
    // If the problem is with single orders, the exception handling code above
    // will do a proper rollback.

    // Error message
    logger << "Error: Caught an exception while solving cluster "
        << cluster << ":" << endl;
    try {throw;}
    catch (const bad_exception&) {logger << "  bad exception" << endl;}
    catch (const exception& e) {logger << "  " << e.what() << endl;}
    catch (...) {logger << "  Unknown type" << endl;}

    // Clean up the operationplans of this cluster
    for (Operation::iterator f=Operation::begin(); f!=Operation::end(); ++f)
      if (f->getCluster() == cluster)
        f->deleteOperationPlans();

    // Clean the list of demands of this cluster
    demands->clear();
  }

  // Message
  if (solver->getLogLevel()>0)
    logger << "End solving cluster " << cluster << " at " << Date::now() << endl;
}


void SolverMRP::SolverMRPdata::solveSafetyStock(SolverMRP* solver)
{
  OperatorDelete cleanup("sweeper", this);
  safety_stock_planning = true;
  if (getLogLevel()>0) logger << "Start safety stock replenishment pass   " << solver->getConstraints() << endl;
  vector< list<Buffer*> > bufs(HasLevel::getNumberOfLevels() + 1);
  for (Buffer::iterator buf = Buffer::begin(); buf != Buffer::end(); ++buf)
    if (buf->getCluster() == cluster
      && ( buf->getMinimum() || buf->getMinimumCalendar()
        || buf->getType() == *BufferProcure::metadata )
      )
      bufs[(buf->getLevel()>=0) ? buf->getLevel() : 0].push_back(&*buf);
  for (vector< list<Buffer*> >::iterator b_list = bufs.begin(); b_list != bufs.end(); ++b_list)
    for (list<Buffer*>::iterator b = b_list->begin(); b != b_list->end(); ++b)
      try
      {
        state->curBuffer = NULL;
        // A quantity of -1 is a flag for the buffer solver to solve safety stock.
        state->q_qty = -1.0;
        state->q_date = Date::infinitePast;
        state->a_cost = 0.0;
        state->a_penalty = 0.0;
        planningDemand = NULL;
        state->curDemand = NULL;
        state->motive = *b;
        state->curOwnerOpplan = NULL;
        // Call the buffer solver
        iteration_count = 0;
        (*b)->solve(*solver, this);
        // Check for excess
        if ((*b)->getType() != *BufferProcure::metadata)
          (*b)->solve(cleanup, this);
        CommandManager::commit();
      }
      catch(...)
      {
        CommandManager::rollback();
      }
  if (getLogLevel()>0) logger << "Finished safety stock replenishment pass" << endl;
  safety_stock_planning = false;
}


DECLARE_EXPORT void SolverMRP::solve(void *v)
{
  // Count how many clusters we have to plan
  int cl = HasLevel::getNumberOfClusters() + 1;

  // Categorize all demands in their cluster
  demands_per_cluster.resize(cl);
  for (Demand::iterator i = Demand::begin(); i != Demand::end(); ++i)
    demands_per_cluster[i->getCluster()].push_back(&*i);

  // Delete of operationplans of the affected clusters
  // This deletion is not multi-threaded... But on the other hand we need to
  // loop through the operations only once (rather than as many times as there
  // are clusters)
  // A multi-threaded alternative would be to hash the operations here, and
  // then delete in each thread.
  if (getLogLevel()>0) logger << "Deleting previous plan" << endl;
  for (Operation::iterator e=Operation::begin(); e!=Operation::end(); ++e)
    e->deleteOperationPlans();

  // Solve in parallel threads.
  // When not solving in silent and autocommit mode, we only use a single
  // solver thread.
  // Otherwise we use as many worker threads as processor cores.
  ThreadGroup threads;
  if (getLogLevel()>0 || !getAutocommit())
    threads.setMaxParallel(1);

  // Register all clusters to be solved
  for (int j = 0; j < cl; ++j)
    threads.add(
      SolverMRPdata::runme,
      new SolverMRPdata(this, j, &(demands_per_cluster[j]))
      );

  // Run the planning command threads and wait for them to exit
  threads.execute();

  // @todo Check the resource setups that were broken - needs to be removed
  for (Resource::iterator gres = Resource::begin(); gres != Resource::end(); ++gres)
    if (gres->getSetupMatrix()) gres->updateSetups();
}


DECLARE_EXPORT void SolverMRP::writeElement(XMLOutput *o, const Keyword& tag, mode m) const
{
  // Writing a reference
  if (m == REFERENCE)
  {
    o->writeElement
    (tag, Tags::tag_name, getName(), Tags::tag_type, getType().type);
    return;
  }

  // Write the complete object
  if (m != NOHEAD && m != NOHEADTAIL) o->BeginObject
    (tag, Tags::tag_name, XMLEscape(getName()), Tags::tag_type, getType().type);

  // Write the fields
  if (constrts != 15) o->writeElement(Tags::tag_constraints, constrts);
  if (plantype != 1) o->writeElement(Tags::tag_plantype, plantype);

  // Parameters
  o->writeElement(tag_iterationthreshold, iteration_threshold);
  o->writeElement(tag_iterationaccuracy, iteration_accuracy);
  o->writeElement(tag_lazydelay, lazydelay);
  o->writeElement(Tags::tag_autocommit, autocommit);

  // User exit
  if (userexit_flow)
    o->writeElement(Tags::tag_userexit_flow, static_cast<string>(userexit_flow));
  if (userexit_demand)
    o->writeElement(Tags::tag_userexit_demand, static_cast<string>(userexit_demand));
  if (userexit_buffer)
    o->writeElement(Tags::tag_userexit_buffer, static_cast<string>(userexit_buffer));
  if (userexit_resource)
    o->writeElement(Tags::tag_userexit_resource, static_cast<string>(userexit_resource));
  if (userexit_operation)
    o->writeElement(Tags::tag_userexit_operation, static_cast<string>(userexit_operation));

  // Write the parent class
  Solver::writeElement(o, tag, NOHEAD);
}


DECLARE_EXPORT void SolverMRP::endElement(XMLInput& pIn, const Attribute& pAttr, const DataElement& pElement)
{
  if (pAttr.isA(Tags::tag_constraints))
    setConstraints(pElement.getInt());
  else if (pAttr.isA(Tags::tag_autocommit))
    setAutocommit(pElement.getBool());
  else if (pAttr.isA(Tags::tag_userexit_flow))
    setUserExitFlow(pElement.getString());
  else if (pAttr.isA(Tags::tag_userexit_demand))
    setUserExitDemand(pElement.getString());
  else if (pAttr.isA(Tags::tag_userexit_buffer))
    setUserExitBuffer(pElement.getString());
  else if (pAttr.isA(Tags::tag_userexit_resource))
    setUserExitResource(pElement.getString());
  else if (pAttr.isA(Tags::tag_userexit_operation))
    setUserExitOperation(pElement.getString());
  else if (pAttr.isA(Tags::tag_plantype))
    setPlanType(pElement.getInt());
  // Less common parameters
  else if (pAttr.isA(tag_iterationthreshold))
    setIterationThreshold(pElement.getDouble());
  else if (pAttr.isA(tag_iterationaccuracy))
    setIterationAccuracy(pElement.getDouble());
  else if (pAttr.isA(tag_lazydelay))
    setLazyDelay(pElement.getTimeperiod());
  else if (pAttr.isA(SolverMRP::tag_rotateresources))
    setRotateResources(pElement.getBool());
  // Default parameters
  else
    Solver::endElement(pIn, pAttr, pElement);
}


DECLARE_EXPORT PyObject* SolverMRP::getattro(const Attribute& attr)
{
  if (attr.isA(Tags::tag_constraints))
    return PythonObject(getConstraints());
  if (attr.isA(Tags::tag_autocommit))
    return PythonObject(getAutocommit());
  if (attr.isA(Tags::tag_userexit_flow))
    return getUserExitFlow();
  if (attr.isA(Tags::tag_userexit_demand))
    return getUserExitDemand();
  if (attr.isA(Tags::tag_userexit_buffer))
    return getUserExitBuffer();
  if (attr.isA(Tags::tag_userexit_resource))
    return getUserExitResource();
  if (attr.isA(Tags::tag_userexit_operation))
    return getUserExitOperation();
  if (attr.isA(Tags::tag_plantype))
    return PythonObject(getPlanType());
  // Less common parameters
  if (attr.isA(tag_iterationthreshold))
    return PythonObject(getIterationThreshold());
  if (attr.isA(tag_iterationaccuracy))
    return PythonObject(getIterationAccuracy());
  if (attr.isA(tag_lazydelay))
    return PythonObject(getLazyDelay());
  if (attr.isA(tag_planSafetyStockFirst))
    return PythonObject(getPlanSafetyStockFirst());
  if (attr.isA(tag_iterationmax))
    return PythonObject(getIterationMax());
  if (attr.isA(SolverMRP::tag_rotateresources))
    return PythonObject(getRotateResources());
  // Default parameters
  return Solver::getattro(attr);
}


DECLARE_EXPORT int SolverMRP::setattro(const Attribute& attr, const PythonObject& field)
{
  if (attr.isA(Tags::tag_constraints))
    setConstraints(field.getInt());
  else if (attr.isA(Tags::tag_autocommit))
    setAutocommit(field.getBool());
  else if (attr.isA(Tags::tag_userexit_flow))
    setUserExitFlow(field);
  else if (attr.isA(Tags::tag_userexit_demand))
    setUserExitDemand(field);
  else if (attr.isA(Tags::tag_userexit_buffer))
    setUserExitBuffer(field);
  else if (attr.isA(Tags::tag_userexit_resource))
    setUserExitResource(field);
  else if (attr.isA(Tags::tag_userexit_operation))
    setUserExitOperation(field);
  else if (attr.isA(Tags::tag_plantype))
    setPlanType(field.getInt());
  // Less common parameters
  else if (attr.isA(tag_iterationthreshold))
    setIterationThreshold(field.getDouble());
  else if (attr.isA(tag_iterationaccuracy))
    setIterationAccuracy(field.getDouble());
  else if (attr.isA(tag_lazydelay))
    setLazyDelay(field.getTimeperiod());
  else if (attr.isA(tag_allowsplits))
    setAllowSplits(field.getBool());
  else if (attr.isA(tag_planSafetyStockFirst))
    setPlanSafetyStockFirst(field.getBool());
  else if (attr.isA(tag_iterationmax))
    setIterationMax(field.getUnsignedLong());
  else if (attr.isA(SolverMRP::tag_rotateresources))
    setRotateResources(field.getBool());
  // Default parameters
  else
    return Solver::setattro(attr, field);
  return 0;
}


DECLARE_EXPORT PyObject* SolverMRP::solve(PyObject *self, PyObject *args)
{
  // Parse the argument
  PyObject *dem = NULL;
  if (args && !PyArg_ParseTuple(args, "|O:solve", &dem)) return NULL;
  if (dem && !PyObject_TypeCheck(dem, Demand::metadata->pythonClass))
  {
    PyErr_SetString(PythonDataException, "solve(d) argument must be a demand");
    return NULL;
  }

  Py_BEGIN_ALLOW_THREADS   // Free Python interpreter for other threads
  try
  {
    SolverMRP* sol = static_cast<SolverMRP*>(self);
    if (!dem)
    {
      // Complete replan
      sol->setAutocommit(true);
      sol->solve();
    }
    else
    {
      // Incrementally plan a single demand
      sol->setAutocommit(false);
      sol->commands.sol = sol;
      static_cast<Demand*>(dem)->solve(*sol, &(sol->commands));
    }
  }
  catch(...)
  {
    Py_BLOCK_THREADS;
    PythonType::evalException();
    return NULL;
  }
  Py_END_ALLOW_THREADS   // Reclaim Python interpreter
  return Py_BuildValue("");
}


DECLARE_EXPORT PyObject* SolverMRP::commit(PyObject *self, PyObject *args)
{
  Py_BEGIN_ALLOW_THREADS   // Free Python interpreter for other threads
  try
  {
    SolverMRP * me = static_cast<SolverMRP*>(self);
    me->scanExcess(&(me->commands));
    me->commands.CommandManager::commit();
  }
  catch(...)
  {
    Py_BLOCK_THREADS;
    PythonType::evalException();
    return NULL;
  }
  Py_END_ALLOW_THREADS   // Reclaim Python interpreter
  return Py_BuildValue("");
}


DECLARE_EXPORT PyObject* SolverMRP::rollback(PyObject *self, PyObject *args)
{
  Py_BEGIN_ALLOW_THREADS   // Free Python interpreter for other threads
  try
  {
    static_cast<SolverMRP*>(self)->commands.rollback();
  }
  catch(...)
  {
    Py_BLOCK_THREADS;
    PythonType::evalException();
    return NULL;
  }
  Py_END_ALLOW_THREADS   // Reclaim Python interpreter
  return Py_BuildValue("");
}

} // end namespace
