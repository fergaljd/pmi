/**
 *  \file pmi/SigmoidRestraintSphere.h
 *  \brief A sigmoid shaped restraint between
 *  residues. To be used with
 *  cross-linking mass-spectrometry data.
 *
 *  Copyright 2007-2013 IMP Inventors. All rights reserved.
 *
 */

#include <IMP/pmi/SigmoidRestraintSphere.h>
#include <IMP/core/XYZR.h>


IMPPMI_BEGIN_NAMESPACE

SigmoidRestraintSphere::SigmoidRestraintSphere(IMP::kernel::Model *m, 
                          IMP::kernel::ParticleIndexAdaptor p1,
                          IMP::kernel::ParticleIndexAdaptor p2,
                          double inflection, double slope, 
                          double amplitude, std::string name):                  
                          Restraint(m, name), 
                          p1_(p1),p2_(p2),inflection_(inflection),
                          slope_(slope),amplitude_(amplitude) {  }                       


double SigmoidRestraintSphere::
                 unprotected_evaluate(DerivativeAccumulator *accum) const
{

    core::XYZR d1(get_model(), p1_);
    core::XYZR d2(get_model(), p2_);
	double dist = IMP::core::get_distance(d1,d2);
    double score= amplitude_*(1.0/(1.0+std::exp(-(dist-inflection_)/slope_)));
    if (accum){};
    
    return score;
}


/* Return all particles whose attributes are read by the restraints. To
   do this, ask the pair score what particles it uses.*/
ModelObjectsTemp  SigmoidRestraintSphere::do_get_inputs() const
{
  ParticlesTemp ret;
  ret.push_back(get_model()->get_particle(p1_));
  ret.push_back(get_model()->get_particle(p2_));
  return ret;
}

IMPPMI_END_NAMESPACE