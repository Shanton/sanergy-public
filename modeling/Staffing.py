import pyscipopt as scip
import pandas as pd
import logging

class Staffing(object):
    N_DAYS = 7
    COL_ROUTE = 'Area'
    COL_DAYS = [str(d) for d in range(0,N_DAYS)]
    COLLECT = 1
    """
    Provide a workforce schedule for a given collection schedule.

    Given: the collection schedule (toilets and every day whether to collect or not and how much waste they accumulate) and (initially) which route/area they belong to
    Output: A list of workers per route/area-day
    """
    def __init__(self, schedule, feces, urine, toilet_routes, staffing_parameters, config):
        """

        Args:
          schedule (dataframe): For each toilet, a column for a day, collect vs not collection, and which area/route it is
          waste (dataframe): For each toilet, a column for a day, the predicted amount of waste accumulated.
          parameters (dict):
            W: weight limit per worker per day
            D: day limit of workdays per week per worker
            N: number of available workers
            NR: minimum number of workers required per route (assume 2, but in fact some need 3 -> fix later)
        """
        self.schedule = schedule
        self.waste = feces + urine
        self.toilet_routes = toilet_routes
        self.parameters = staffing_parameters
        self.config = config
        self.log = logging.getLogger("Sanergy Collection Optimizer")


    def preprocess(self):
        """
        Define the variables needed or useful for optimization
        T: number of toilets (from schedule)
        routes: ... (from schedule)
        """
        today = self.schedule.columns.values.min()
        self.next_days = self.schedule.columns
        self.routes = self.toilet_routes[self.config['cols']['route']].unique()
        self.tr_valid = self.toilet_routes.loc[self.toilet_routes[self.config['cols']['route']] != "None" ] #Drop the none-routes....
        #Route-toilet dictionary
        #TODO: There will probably be an overlap...
        rtd = { r:self.tr_valid.loc[(self.tr_valid[self.config['cols']['route']]==r) & (self.tr_valid[self.config['cols']['date']] <= today), self.config['cols']['toiletname']].unique() for r in self.routes}

        #Only include the routes that have at least one toilet to collect
        #Select toilets which lie on route r
        self.is_the_route_collected_on_day = {(d,r) : self.schedule.loc[self.schedule.index.isin(rtd[r]) ,d].sum() > 0 for d in self.next_days for r in self.routes}
        #print(self.is_the_route_collected_on_day)
        self.route_waste = {(d,r) : self.waste.loc[((self.schedule.index.isin(rtd[r])) & (self.schedule[d]==self.COLLECT)),d].sum() for d in self.next_days for r in self.routes}
        #print(self.route_waste)

    def staff(self):
        """
        Produce the staffing /workforce schedule.
        Minimize workers needed, given the constraints
        Note that the problem can be essentially decompose by area as we assume that workers don't cross areas in one day (and possibly the entire week?).

        Step 1 [DONE]:
          * Routes given, just assign the number of workers depending on how much waste we expect?
          * In fact, one could consider each area to be a route and it will give a number of people assigned to an area, assuming they can then determine and divide the routes among themselves.
          * Alternatively, could determine the routes by just clustering toilets, putting together toilets so that we just about fill up Worker's carry limit per route
          * Constraints on waste lifted/carried (assume the crew leader can lift and then each of the workers)
          * Use one worker at most 5 days a week?

         z_crd: collector c assigned to route r available on day d. A limited number of workers?
         gamma_td: toilet t should be collected on day d
         gamma_rd: route r should be collected on day d. gamma_rd = max_t gamma_td * chi_rt. If a route coincides with an area, then can have gamma_rd = 1 (assuming every area has some toilets to be collected?)
         lambda_rd: Collector lower bound per route... normally 2, 3 for handcarts
         chi_rt: toilet t lies on route r
         w_rd: weight (predicted) on route r on day d. w_rd = sum_t chi_rt * w_td
         W: weight limit per worker per day

         min_{z_crd} sum z_crd
         sum_rd z_crd <= 5 forall c
         sum_c z_crd >= 2*gamma_rd forall r,d #Assign 2+ workers if a route is to be collected. Needs to have at least 2, we know... for the wheelbarrow routes, need to have at least three?
         sum_c z_crd * W >= w_rd forall r, d

        Step 2:
          * Upper bound on workers and a penalty for uncollectable toilets (flexible workforce vs toilet overflows)
          * Extra constraints on worker unavailability

        Step 3:
        #TODO
          * "Routing" within areas. Consider just aerial distances between toilets. The thing is, we could consolidate some routes when we only collect occasionally.
          * Collection window constraints (because the waste accumulates when?)
          * Constraints on the distance traveled by a worker

        Step 4: Other constraints/objectives
          * Training (have workers rotate through different areas)
        """
        if self.schedule is None or self.waste is None:
            self.log.warning("The staffing routine has not received scheduling or waste prediction data. The workforce schedule will not be created.")
            return( [None, None, None] )

        self.preprocess()


        s = scip.Model("Staffing")
        s.hideOutput()
        s.setMinimize()

        #Vars: z_crd: collector c assigned to route r for day d
        assign_vars = {}
        for c in range(0,self.parameters['N']):
            for i_r, r in enumerate(self.routes):
                for d in self.next_days:
                    v_name = 'z' + str(c) + str(i_r) + str(d)
                    #This also handles the objective function...
                    assign_vars[c,r,d] = s.addVar(v_name, vtype='B', obj=1.0)


        #Constraints
        for c in range(0,self.parameters['N']):
            #1) Collector workday limits
            w_name = 'Worker_' + str(c)
            coeffs_worker = {assign_vars[(c,r,d)] : 1 for d in self.next_days for i_r,r in enumerate(self.routes)}
            s.addCons(coeffs = coeffs_worker , rhs=self.parameters['D'], name=w_name)
        for d in self.next_days:
            for i_r,r in enumerate(self.routes):
                #2) Collector weight limits on routes. For each route: assign 2+ workers and also more than the predicted weight per the route
                #3) Assign n+ workers on the route
                route_weight_name = 'Route_Weight_' + str(i_r) + "_" + str(d)
                route_collector_minimum_name = 'Route_Minimum_' + str(i_r) + "_" + str(d)
                coeffs_weight = {assign_vars[(c,r,d)] : 1 for c in range(0,self.parameters['N'])} #sum_c z_crd >= w_rd / W
                coeffs_collectors = {assign_vars[(c,r,d)] : 1 for c in range(0,self.parameters['N'])}

                weight_limit =  self.is_the_route_collected_on_day[d,r]  * self.route_waste[d, r] / self.parameters['W']
                collect_limit =  self.is_the_route_collected_on_day[d,r]  * self.parameters['NR']
                s.addCons(coeffs = coeffs_weight, lhs =weight_limit, rhs=None, name= route_weight_name)
                s.addCons(coeffs = coeffs_collectors, lhs = collect_limit, rhs=None, name= route_collector_minimum_name)

        #Write down the formulation to make sure it was formulated correctly.
        #s.writeProblem()
        #Objective function
        #Done: See in Vars
        s.optimize()
        vars = s.getVars()
        #for v in vars[0:50]:
        #    print(s.getVal(v))


        roster = self.createRoster(s,assign_vars)
        self.log.debug(s.printStatistics())
        return(roster, s, assign_vars)


    def createRoster(self, optimizedModel, vars):
        """
        Create a roster per route/area, currently only giving the number of people needed per day.

        args:
          optimizedModel: Passed from the staffing model.

        returns:
          DataFrame roster: a row for each route, a column for each day, the value indicates how many collectors are needed for that day and route
        """
        roster = pd.DataFrame(index = self.routes, columns = self.next_days)
        for r in self.routes:
            for d in self.next_days:
                roster.loc[r,d] = int(round(reduce(lambda x,y: x+y, [optimizedModel.getVal(vars[i_worker,r,d]) for i_worker in range(0,self.parameters['N'])])))

        return(roster)
