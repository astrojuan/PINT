# timing_model.py
# Defines the basic timing model interface classes
import string
from warnings import warn
from .parameter import Parameter
from ..phase import Phase

class Parameter(object):
    """
    Parameter(name=None, value=None, units=None, description=None, 
                uncertainty=None, frozen=True, continuous=True, aliases=[],
                parse_value=float, print_value=str)

        Class describing a single timing model parameter.  Takes the following
        inputs:

        name is the name of the parameter.

        value is the current value of the parameter.

        units is a string giving the units.

        description is a short description of what this parameter means.

        uncertainty is the current uncertainty of the value.

        frozen is a flag specifying whether "fitters" should adjust the
          value of this parameter or leave it fixed.

        continuous is flag specifying whether phase derivatives with 
          respect to this parameter exist.

        aliases is an optional list of strings specifying alternate names
          that can also be accepted for this parameter.

        parse_value is a function that converts string input into the
          appropriate internal representation of the parameter (typically
          floating-point but could be any datatype).

        print_value is a function that converts the internal value to
          a string for output.

    """

    def __init__(self, name=None, value=None, units=None, description=None, 
            uncertainty=None, frozen=True, aliases=[], continuous=True,
            parse_value=fortran_float, print_value=str):
        self.value = value
        self.name = name
        self.units = units
        self.description = description
        self.uncertainty = uncertainty
        self.frozen = frozen
        self.continuous = continuous
        self.aliases = aliases
        self.parse_value=parse_value
        self.print_value=print_value

    def __str__(self):
        out = self.name
        if self.units is not None:
            out += " (" + str(self.units) + ")"
        out += " " + self.print_value(self.value)
        if self.uncertainty is not None:
            out += " +/- " + str(self.uncertainty)
        return out

    def set(self,value):
        """
        Parses a string 'value' into the appropriate internal representation
        of the parameter.
        """
        self.value = self.parse_value(value)

    def add_alias(self, alias):
        """
        Add a name to the list of aliases for this parameter.
        """
        self.aliases.append(alias)

    def help_line(self):
        """
        Return a help line containing param name, description and units.
        """
        out = "%-12s %s" % (self.name, self.description)
        if self.units is not None:
            out += ' (' + str(self.units) + ')'
        return out

    def as_parfile_line(self):
        """
        Return a parfile line giving the current state of the parameter.
        """
        # Don't print unset parameters
        if self.value is None: 
            return ""
        line = "%-15s %25s" % (self.name, self.print_value(self.value))
        if self.uncertainty is not None:
            line += " %d %s" % (0 if self.frozen else 1, str(self.uncertainty))
        elif not self.frozen:
            line += " 1" 
        return line + "\n"

    def from_parfile_line(self,line):
        """
        Parse a parfile line into the current state of the parameter.
        Returns True if line was successfully parsed, False otherwise.
        """
        try:
            k = line.split()
            name = k[0].upper()
        except:
            return False
        # Test that name matches
        if (name != self.name) and (name not in self.aliases):
            return False
        if len(k)<2:
            return False
        if len(k)>=2:
            self.set(k[1])
        if len(k)>=3:
            if int(k[2])>0: 
                self.frozen = False
        if len(k)==4:
            self.uncertainty = fortran_float(k[3])
        return True

class MJDParameter(Parameter):
    """
    MJDParameter(self, name=None, value=None, units=None, description=None, 
            uncertainty=None, frozen=True, aliases=[],
            parse_value=fortran_float, print_value=str):

    This is a Parameter type that is specific to MJD values.
    """

    def __init__(self, name=None, value=None, description=None, 
            uncertainty=None, frozen=True, continuous=True, aliases=[],
            parse_value=fortran_float, print_value=str):
        super(MJDParameter,self).__init__(name=name,value=value,
                units="MJD", description=description,
                uncertainty=uncertainty, frozen=frozen, 
                continuous=continuous,
                aliases=aliases,
                parse_value=time_from_mjd_string,
                print_value=time_to_mjd_string)

class TimingModel(object):

    def __init__(self):
        self.params = []  # List of model parameter names
        self.delay_funcs = [] # List of delay component functions
        self.phase_funcs = [] # List of phase component functions

        # Derivatives of phase and delay with respect to params
        self.delay_derivs = {}
        self.phase_derivs = {}
        # Derivative of phase with respect to pulsar time
        self.d_phase_funcs = []

        self.add_param(Parameter(name="PSR",
            units=None,
            description="Source name",
            aliases=["PSRJ","PSRB"],
            parse_value=str))

    def setup(self):
        pass

    def add_param(self, param):
        # If the parameter has already been defined this is an error
        if hasattr(self,param.name):
            raise DuplicateParameter(param.name)
        setattr(self, param.name, param)
        self.params += [param.name,]
        if param.continuous:
            # Set up entries for derivative functions
            self.delay_derivs[param.name] = []
            self.phase_derivs[param.name] = []

    def param_help(self):
        """
        Print help lines for all available parameters in model.
        """
        print "Available parameters for ", self.__class__
        for par in self.params:
            print getattr(self,par).help_line()

    def phase(self, toa):
        """
        Return the model-predicted pulse phase for the given toa.
        """
        # First compute the delay to "pulsar time"
        delay = self.delay(toa)
        phase = Phase(0,0.0)

        # Then compute the relevant pulse phase
        for pf in self.phase_funcs:
            phase += pf(toa,delay)  # This is just a placeholder until we
                                    # define what datatype 'toa' has, and
                                    # how to add/subtract from it, etc.
        return phase

    def delay(self, toa):
        """
        Return the total delay which will be subtracted from the given
        TOA to get time of emission at the pulsar.
        """
        delay = 0.0
        for df in self.delay_funcs:
            delay += df(toa)
        return delay

    def d_phase_d_tpulsar(self,toa):
        """
        Return the derivative of phase wrt time at the pulsar.
        NOT Implemented
        """
        pass

    def d_phase_d_toa(self,toa):
        """
        Return the derivative of phase wrt TOA (ie the current apparent
        spin freq of the pulsar at the observatory).
        NOT Implemented yet.
        """
        pass

    def d_phase_d_param(self,toa,param):
        """
        Return the derivative of phase with respect to the parameter.
        NOTE, not implemented yet
        """
        result = 0.0
        # TODO need to do correct chain rule stuff wrt delay derivs, etc
        # Is it safe to assume that any param affecting delay only affects
        # phase indirectly (and vice-versa)??
        return result

    def d_delay_d_param(self,toa,param):
        """
        Return the derivative of delay with respect to the parameter.
        """
        result = 0.0
        for f in self.delay_derivs[param]:
            result += f(toa)
        return result

    def __str__(self):
        result = ""
        for par in self.params:
            result += str(getattr(self,par)) + "\n"
        return result

    def as_parfile(self):
        """
        Returns a parfile representation of the entire model as a string.
        """
        result = ""
        for par in self.params:
            result += getattr(self,par).as_parfile_line()
        return result

    def read_parfile(self, filename):
        """
        Read values from the specified parfile into the model parameters.
        """
        pfile = open(filename,'r')
        for l in map(string.strip,pfile.readlines()):
            # Skip blank lines
            if not l: continue
            # Skip commented lines
            if l.startswith('#'): continue
            parsed = False
            for par in self.params:
                if getattr(self,par).from_parfile_line(l):
                    parsed = True
            if not parsed:
                warn("Unrecognized parfile line '%s'" % l)

        # The "setup" functions contain tests for required parameters or
        # combinations of parameters, etc, that can only be done
        # after the entire parfile is read
        self.setup()

def generate_timing_model(name,components):
    """
    Returns a timing model class generated from the specified 
    sub-components.  The return value is a class type, not an instance,
    so needs to be called to generate a usable instance.  For example:

    MyModel = generate_timing_model("MyModel",(Astrometry,Spindown))
    my_model = MyModel()
    my_model.read_parfile("J1234+1234.par")
    """
    # TODO could test here that all the components are derived from 
    # TimingModel?
    return type(name, components, {})

class TimingModelError(Exception):
    """
    Generic base class for timing model errors.
    """
    pass

class MissingParameter(TimingModelError):
    """
    This exception should be raised if a required model parameter was 
    not included.

    Attributes:
      module = name of the model class that raised the error
      param = name of the missing parameter
      msg = additional message
    """
    def __init__(self,module,param,msg=None):
        self.module = module
        self.param = param
        self.msg = msg

    def __str__(self):
        result = self.module + "." + self.param
        if self.msg is not None:
            result += "\n  " + self.msg
        return result

class DuplicateParameter(TimingModelError):
    """
    This exception is raised if a model parameter is defined (added)
    multiple times.
    """
    def __init__(self,param,msg=None):
        self.param = param
        self.msg = msg

    def __str__(self):
        result = self.param
        if self.msg is not None:
            result += "\n  " + self.msg
        return result

