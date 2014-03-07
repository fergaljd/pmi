#!/usr/bin/env python
import IMP
import IMP.core
import IMP.base
import IMP.algebra
import IMP.atom
import IMP.display
import IMP.pmi
from math import pi,sqrt

from operator import itemgetter
import IMP.pmi.tools
import IMP.pmi.output
import IMP.rmf
import RMF




class Representation():
    #Authors: Peter Cimermancic, Riccardo Pellarin, Charles Greenberg
    
    '''
    This class creates the molecular hierarchies, representation,
    sequence connectivity for the various involved proteins and
    nucleic acid macromolecules:

    Create a protein, DNA or RNA, represent it as a set of connected balls of appropriate
    radii and number of residues, pdb at given resolution(s), or ideal helices.

    To initialize the class:

    m                the model
    upperharmonic    Bool This flag uses either harmonic (False)
                     or upperharmonic (True) in the intra-pair
                     connectivity restraint. Default is True.
    disorderedlength Bool This flag uses either disordered length
                     calculated for random coil peptides (True) or zero
                     surface-to-surface distance between beads (False)
                     as optimal distance for the sequence connectivity
                     restraint. Default is False.

    How to use the SimplifiedModel class (typical use):

    see test/test_hierarchy_contruction.py

    examples:

    1) Create a chain of helices and flexible parts

    c_1_119   =self.add_component_necklace("prot1",1,119,20)
    c_120_131 =self.add_component_ideal_helix("prot1",resolutions=[1,10],resrange=(120,131))
    c_132_138 =self.add_component_beads("prot1",[(132,138)])
    c_139_156 =self.add_component_ideal_helix("prot1",resolutions=[1,10],resrange=(139,156))
    c_157_174 =self.add_component_beads("prot1",[(157,174)])
    c_175_182 =self.add_component_ideal_helix("prot1",resolutions=[1,10],resrange=(175,182))
    c_183_194 =self.add_component_beads("prot1",[(183,194)])
    c_195_216 =self.add_component_ideal_helix("prot1",resolutions=[1,10],resrange=(195,216))
    c_217_250 =self.add_component_beads("prot1",[(217,250)])


    self.set_rigid_body_from_hierarchies(c_120_131)
    self.set_rigid_body_from_hierarchies(c_139_156)
    self.set_rigid_body_from_hierarchies(c_175_182)
    self.set_rigid_body_from_hierarchies(c_195_216)

    clist=[c_1_119,c_120_131,c_132_138,c_139_156,c_157_174,c_175_182,c_183_194,c_195_216,
      c_217_250]

    self.set_chain_of_super_rigid_bodies(clist,2,3)

    self.set_super_rigid_bodies(["prot1"])

    '''

    def __init__(self,m,upperharmonic=True,disorderedlength=True):

        # this flag uses either harmonic (False) or upperharmonic (True)
        # in the intra-pair connectivity restraint. Harmonic is used whe you want to
        # remove the intra-ev term from energy calculations, e.g.:
        # upperharmonic=False
        # ip=self.get_connected_intra_pairs()
        # ev.add_excluded_particle_pairs(ip)

        self.upperharmonic=upperharmonic
        self.disorderedlength=disorderedlength
        self.rigid_bodies=[]
        self.fixed_rigid_bodies=[]
        self.floppy_bodies=[]
        # self.super_rigid_bodies is a list of tuples.
        # each tuple, corresponding to a particular super rigid body
        # the tuple is (super_rigid_xyzs,super_rigid_rbs)
        # where super_rigid_xyzs are the flexible xyz particles
        # and super_rigid_rbs is the list of rigid bodies.
        self.super_rigid_bodies=[]
        self.output_level="low"
        self.label="None"

        self.maxtrans_rb=2.0
        self.maxrot_rb=0.04
        self.maxtrans_srb=2.0
        self.maxrot_srb=0.2
        self.rigidbodiesarefixed=False
        self.maxtrans_fb=3.0
        self.resolution=10.0
        self.bblenght=100.0
        self.kappa=100.0
        self.m = m

        self.representation_is_modified=False
        self.unmodeledregions_cr_dict={}
        self.sortedsegments_cr_dict={}
        self.prot=IMP.atom.Hierarchy.setup_particle(IMP.Particle(self.m))
        self.connected_intra_pairs=[]
        self.hier_dict={}
        self.color_dict={}
        self.sequence_dict={}
        self.hier_geometry_pairs={}
        self.hier_db=IMP.pmi.tools.HierarchyDatabase()
        #this dictionary stores the hierarchies by component name and representation type
        #self.hier_representation[name][representation_type]
        #where representation type is Res:X, Beads, Densities, Representation, etc...
        self.hier_representation={}
        self.hier_resolution={}
        #reference structures is a dictionary that contains the coordinates of
        #structures that are used to calculate the rmsd
        self.reference_structures={}
        self.elements={}
        self.linker_restraints=IMP.RestraintSet(self.m,"linker_restraints")
        self.linker_restraints_dict={}
        self.threetoone={'ALA':'A','ARG':'R','ASN':'N','ASP':'D',
                         'CYS':'C','GLU':'E','GLN':'Q','GLY':'G',
                         'HIS':'H','ILE':'I','LEU':'L','LYS':'K',
                         'MET':'M','PHE':'F','PRO':'P','SER':'S',
                         'THR':'T','TRP':'W','TYR':'Y','VAL':'V','UNK':'X'}

        self.onetothree = dict((v,k) for k, v in self.threetoone.iteritems())

        self.residuenamekey = IMP.kernel.StringKey("ResidueName")

    def set_label(self,label):
        self.label=label

    def create_component(self,name,color=None):
        protein_h = IMP.atom.Molecule.setup_particle(IMP.Particle(self.m))
        protein_h.set_name(name)
        self.hier_dict[name]=protein_h
        self.hier_representation[name]={}
        self.hier_db.add_name(name)
        self.prot.add_child(protein_h)
        self.color_dict[name]=color
        self.elements[name]=[]

    # Deprecation warning

    def add_component_name(self,*args, **kwargs):
            IMP.pmi.tools.print_deprecation_warning("add_component_name","create_component")
            self.create_component(*args, **kwargs)

    def get_component_names(self):
        return self.hier_dict.keys()

    def add_component_sequence(self,name,filename,id=None,format="FASTA"):
        '''
        give the component name, the fasta filename,
        and the id stored in the fasta file (i.e., the header)
        If the id is not provided, it will assume the same compoennt
        name.
        '''
        from Bio import SeqIO
        handle = open(filename, "rU")
        record_dict = SeqIO.to_dict(SeqIO.parse(handle, "fasta"))
        handle.close()
        if id is None: id=name
        try:
           length=len(record_dict[id].seq)
        except KeyError:
           print "add_component_sequence: id %s not found in fasta file" % id
           exit()
        self.sequence_dict[name]=str(record_dict[id].seq).replace("*","")
        self.elements[name].append((length,length," ","end"))

    def autobuild_model(self,name,pdbname,chain,
                                      resolutions=None,resrange=None,
                                      missingbeadsize=20,
                                      beadsize=None, #this is deprecated
                                      color=None,pdbresrange=None,offset=0,
                                      show=False,isnucleicacid=False,
                                      attachbeads=False):

        if not beadsize is None:
           IMP.pmi.tools.print_deprecation_warning("beadsize","missingbeadsize")

        self.representation_is_modified=True
        outhiers=[]

        if color is None:
           color=self.color_dict[name]
        else:
           self.color_dict[name]=color

        if resolutions is None:
           resolutions=[1]
        print "autobuild_model: constructing %s from pdb %s and chain %s" % (name,pdbname,str(chain))

        #get the initial and end residues of the pdb
        t=IMP.atom.read_pdb( pdbname, self.m,
        IMP.atom.AndPDBSelector(IMP.atom.ChainPDBSelector(chain),IMP.atom.CAlphaPDBSelector()))

        #find start and end indexes

        start = IMP.atom.Residue(t.get_children()[0].get_children()[0]).get_index()
        end   = IMP.atom.Residue(t.get_children()[0].get_children()[-1]).get_index()

        #check if resrange was defined, otherwise
        #use the sequence, or the pdb resrange

        if resrange is None:
           if name in self.sequence_dict:
              resrange=(1,len(self.sequence_dict[name]))
           else:
              resrange=(start+offset,end+offset)
        else:
           start=resrange[0]-offset
           end=resrange[1]-offset

        gaps=IMP.pmi.tools.get_residue_gaps_in_hierarchy(t,resrange[0],resrange[1])
        xyznter=IMP.pmi.tools.get_closest_residue_position(t,start,terminus="N")
        xyzcter=IMP.pmi.tools.get_closest_residue_position(t,end,terminus="C")

        #construct pdb fragments and intervening beads
        for n,g in enumerate(gaps):
            first=g[0]+offset
            last=g[1]+offset
            if g[2]=="cont":
               print "autobuild_model: constructing fragment %s from pdb" % (str((first,last)))
               outhiers+=self.add_component_pdb(name,pdbname,
                                                chain,resolutions=resolutions,
                                                color=color,cacenters=True,
                                                resrange=(first,last),
                                                offset=offset,isnucleicacid=isnucleicacid)
            elif g[2]=="gap" and n>0:
               print "autobuild_model: constructing fragment %s as a bead" % (str((first,last)))
               parts=self.hier_db.get_particles_at_closest_resolution(name,first-1,1)
               xyz=IMP.core.XYZ(parts[0]).get_coordinates()
               outhiers+=self.add_component_necklace(name,first,last,missingbeadsize,incoord=xyz)

            elif g[2]=="gap" and n==0:
               #add pre-beads
               print "autobuild_model: constructing fragment %s as a bead" % (str((first,last)))
               outhiers+=self.add_component_necklace(name,first,last,missingbeadsize,incoord=xyznter)

        return outhiers

    # Deprecation warning

    def autobuild_pdb_and_intervening_beads(self,*args, **kwargs):
            IMP.pmi.tools.print_deprecation_warning("autobuild_pdb_and_intervening_beads","autobuild_model")
            r=self.autobuild_model(*args, **kwargs)
            return r

    def add_component_pdb(self,name,pdbname,chain,resolutions,color=None,resrange=None,offset=0,
                                   cacenters=True,show=False,isnucleicacid=False,readnonwateratoms=False):

        '''
        This method reads a pdb, constructs the fragments corresponding to contiguous senquence stretches,
        and returns a list of hierarchies.

        name:             (string) the name of the component
        pdbname:          (string) the name of the pdb
        chain:            (string or integer) can be either a string (eg, "A")
                          or an integer (eg, 0 or 1) in case you want
                          to get the corresponding chain number in the pdb.
        resolutions:      (integers) a list of integers that corresponds to the resolutions that have to be
                          generated
        color:            (float from 0 to 1, optional default=None): the color applied to the hierarchies generated
                          by this method
        resrange:         (tuple of integers, optional, default=None): specifies the residue range to extract from the pdb
                          it is a tuple (beg,end). If not specified, it takes all residues belonging to
                          the specified chain.
        offset:           (integer, optional, default=0): specifies the residue index offset to be applied when reading the pdb
        cacenters:        (boolean, optional, default=True): if True generates resolution=1 beads centered on C-alpha atoms.
        show:             (boolean, optional, default=False): print out the molecular hierarchy at the end.
        isnucleicacid:    (boolean, optional, default=False): use True if you're reading a pdb with nucleic acid.
        readnonwateratoms:(boolean, optional, default=False): if True fixes some pathological pdb.

        '''

        self.representation_is_modified=True
        if color is None:
           # if the color is not passed, then get the stored color
           color=self.color_dict[name]
        protein_h=self.hier_dict[name]
        outhiers=[]

        if type(chain)==str:
           #if the chainid is a string
           if not readnonwateratoms:
              t=IMP.atom.read_pdb( pdbname, self.m,
              IMP.atom.AndPDBSelector(IMP.atom.ChainPDBSelector(chain),IMP.atom.NonWaterNonHydrogenPDBSelector()))
           else:
              t=IMP.atom.read_pdb( pdbname, self.m,
              IMP.atom.AndPDBSelector(IMP.atom.ChainPDBSelector(chain),IMP.atom.NonWaterNonHydrogenPDBSelector()))
           #get the first and last residue
           start = IMP.atom.Residue(t.get_children()[0].get_children()[0]).get_index()
           end   = IMP.atom.Residue(t.get_children()[0].get_children()[-1]).get_index()
           c=IMP.atom.Chain(IMP.atom.get_by_type(t, IMP.atom.CHAIN_TYPE)[0])

        elif type(chain)==int:
           #if the chainid is a number, get the corresponding chain number from the pdb
           if not readnonwateratoms:
              s=IMP.atom.read_pdb( pdbname, self.m, IMP.atom.NonWaterNonHydrogenPDBSelector())
           else:
              s=IMP.atom.read_pdb( pdbname, self.m, IMP.atom.NonWaterNonHydrogenPDBSelector())
           t=IMP.atom.Chain(IMP.atom.get_by_type(s, IMP.atom.CHAIN_TYPE)[chain])
           #get the first and last residue
           start = IMP.atom.Residue(t.get_children()[0]).get_index()
           end   = IMP.atom.Residue(t.get_children()[-1]).get_index()
           c=t
           chain=t.get_id()
           del s,t

        if not resrange is None:
           if resrange[0]>start: start=resrange[0]
           if resrange[1]<end:   end=resrange[1]


        if not isnucleicacid:
           #do what you have to do for proteins
           sel=IMP.atom.Selection(c,residue_indexes=range(start,end+1),atom_type=IMP.atom.AT_CA)

        else:
           #do what you have to do for nucleic-acids
           sel=IMP.atom.Selection(c,residue_indexes=range(start,end+1),atom_type=IMP.atom.AT_P)


        ps=sel.get_selected_particles()
        if len(ps)==0:
           print "ERROR add_component_pdb: %s no residue found in pdb %s chain %s that overlaps with the queried stretch %s-%s" \
                 % (name,pdbname,str(chain),str(resrange[0]),str(resrange[1]))
           exit()
        c0=IMP.atom.Chain.setup_particle(IMP.Particle(self.m),"X")

        for p in ps:
            par=IMP.atom.Atom(p).get_parent()
            ri=IMP.atom.Residue(par).get_index()
            IMP.atom.Residue(par).set_index(ri+offset)
            c0.add_child(par)
        start=start+offset
        end=end+offset

        self.elements[name].append((start,end,pdbname.split("/")[-1]+":"+chain,"pdb"))

        outhiers+=self.coarse_hierarchy(name,start,end,resolutions,isnucleicacid,c0,protein_h,"pdb",color)

        if show:
           IMP.atom.show_molecular_hierarchy(protein_h)

        del c; del c0; del t

        return outhiers

    def add_component_ideal_helix(self,name,resolutions,resrange,color=None,show=False):

        self.representation_is_modified=True
        from math import pi,cos,sin

        protein_h=self.hier_dict[name]
        outhiers=[]
        if color is None:
           color=self.color_dict[name]

        start=resrange[0]
        end=resrange[1]
        self.elements[name].append((start,end," ","helix"))
        c0=IMP.atom.Chain.setup_particle(IMP.Particle(self.m),"X")
        for n,res in enumerate(range(start,end+1)):
            if name in self.sequence_dict:
               try:
                  rtstr=self.onetothree[self.sequence_dict[name][ds_frag[0]]]
               except:
                  rtstr="UNK"
               rt=IMP.atom.ResidueType(rtstr)
            else:
              rt=IMP.atom.ResidueType("ALA")
            r=IMP.atom.Residue.setup_particle(IMP.Particle(self.m),rt,res)
            p=IMP.Particle(self.m)
            d=IMP.core.XYZR.setup_particle(p)
            x=2.3*cos(n*2*pi/3.6)
            y=2.3*sin(n*2*pi/3.6)
            z=6.2/3.6/2*n*2*pi/3.6
            d.set_coordinates(IMP.algebra.Vector3D(x,y,z))
            d.set_radius(2.9)
            #print d
            a=IMP.atom.Atom.setup_particle(p,IMP.atom.AT_CA)
            r.add_child(a)
            c0.add_child(r)

        outhiers+=self.coarse_hierarchy(name,start,end,resolutions,False,c0,protein_h,"helix",color)

        if show:
           IMP.atom.show_molecular_hierarchy(protein_h)

        del c0
        return outhiers

    def add_component_beads(self,name,ds,colors=None,incoord=None):

        from math import pi
        self.representation_is_modified=True

        protein_h=self.hier_dict[name]
        outhiers=[]
        if colors is None:
           colors=[self.color_dict[name]]

        for n,dss in enumerate(ds):
            ds_frag=(dss[0],dss[1])
            self.elements[name].append((dss[0],dss[1]," ","bead"))
            prt=IMP.Particle(self.m)
            if ds_frag[0]==ds_frag[1]:
               #if the bead represent a single residue
               if name in self.sequence_dict:
                  try:
                     rtstr=self.onetothree[self.sequence_dict[name][ds_frag[0]]]
                  except:
                     rtstr="UNK"
                  rt=IMP.atom.ResidueType(rtstr)
               else:
                  rt=IMP.atom.ResidueType("ALA")
               h=IMP.atom.Residue.setup_particle(prt,rt,ds_frag[0])
               h.set_name(name+'_%i_bead' % (ds_frag[0]))
               prt.set_name(name+'_%i_bead' % (ds_frag[0]))
               resolution=1
            else:
               h=IMP.atom.Fragment.setup_particle(prt)
               h.set_name(name+'_%i-%i_bead' % (ds_frag[0],ds_frag[1]))
               prt.set_name(name+'_%i-%i_bead' % (ds_frag[0],ds_frag[1]))
               h.set_residue_indexes(range(ds_frag[0],ds_frag[1]+1))
               resolution=len(h.get_residue_indexes())
            if "Beads" not in self.hier_representation[name]:
                 root=IMP.atom.Hierarchy.setup_particle(IMP.Particle(self.m))
                 root.set_name("Beads")
                 self.hier_representation[name]["Beads"]=root
                 protein_h.add_child(root)
            self.hier_representation[name]["Beads"].add_child(h)

            for kk in range(ds_frag[0],ds_frag[1]+1):
                self.hier_db.add_particles(name,kk,resolution,[h])

            try:
                clr=IMP.display.get_rgb_color(colors[n])
            except:
                clr=IMP.display.get_rgb_color(colors[0])

            IMP.display.Colored.setup_particle(prt,clr)

            #decorate particles according to their resolution
            IMP.pmi.Resolution.setup_particle(prt,resolution)

            IMP.core.XYZR.setup_particle(prt)
            ptem=IMP.core.XYZR(prt)
            mass =IMP.atom.get_mass_from_number_of_residues(resolution)
            if resolution==1:
               try:
                   vol=IMP.atom.get_volume_from_residue_type(rt)
               except IMP.base.ValueException:
                   vol=IMP.atom.get_volume_from_residue_type(IMP.atom.ResidueType("ALA"))
               radius=IMP.algebra.get_ball_radius_from_volume_3d(vol)
               IMP.atom.Mass.setup_particle(prt,mass)
               ptem.set_radius(radius)
            else:
               volume=IMP.atom.get_volume_from_mass(mass)
               radius=0.8*(3.0/4.0/pi*volume)**(1.0/3.0)
               IMP.atom.Mass.setup_particle(prt,mass)
               ptem.set_radius(radius)
            try:
                if not tuple(incoord) is None: ptem.set_coordinates(incoord)
            except TypeError: pass
            IMP.pmi.Uncertainty.setup_particle(prt,radius)
            IMP.pmi.Symmetric.setup_particle(prt,0)
            self.floppy_bodies.append(prt)
            IMP.core.XYZ(prt).set_coordinates_are_optimized(True)
            outhiers+=[h]

        return outhiers

    def add_component_necklace(self,name,begin,end,length,incoord=None):
        '''
        generates a string of beads with given length
        '''
        self.representation_is_modified=True
        outhiers=[]
        for chunk in list(IMP.pmi.tools.list_chunks_iterator(range(begin,end+1),length)):
            outhiers+=self.add_component_beads(name,[(chunk[0],chunk[-1])],incoord=incoord)
        return outhiers

    def add_component_density(self,name,hierarchies=None,selection_tuples=None,
                              particles=None,
                              resolution=0.0,num_components=10,
                              inputfile=None,outputfile=None,
                              outputmap=None,
                              kernel_type=None,
                              covariance_type='full',voxel_size=1.0,
                              out_hier_name='',
                              sampled_points=1000000,num_iter=100,
                              multiply_by_total_mass=True,
                              transform=None,
                              intermediate_map_fn=None):

        '''
        This function sets up a GMM for this component.
        Can specify input GMM file or it will be computed.
        name:                   component name
        hierarchies:            set up GMM for some hierarchies
        selection_tuples:       (list of tuples) example (first_residue,last_residue,component_name)
        particles:              set up GMM for particles directly
        resolution:             usual PMI resolution for selecting particles from the hierarchies
        inputfile:              read the GMM from this file
        outputfile:             fit and write the GMM to this file (text)
        outputmap:              after fitting, create GMM density file (mrc)
        kernel_type:            for creating the intermediate density (points are sampled to make GMM)
                                  options are IMP.em.GAUSSIAN, IMP.em.SPHERE, and IMP.em.BINARIZED_SPHERE
        covariance_type:        for fitting the GMM. options are 'full', 'diagonal' and 'spherical'
        voxel_size:             for creating the intermediate density map and output map.
                                  lower number increases accuracy but also rasterizing time grows
        out_hier_name:          name of the output density hierarchy
        sampled_points:         number of points to sample. more will increase accuracy and fitting time
        num_iter:               num GMM iterations. more will increase accuracy and fitting time
        multiply_by_total_mass: multiply the weights of the GMM by this value (only works on creation!)
        transform:              for input file only, apply a transformation (eg for multiple copies same GMM)
        intermediate_map_fn:    for debugging, this will write the itermediate (simulated) map
        '''

        import IMP.isd_emxl
        import IMP.isd_emxl.gmm_tools
        import numpy as np
        import sys
        import IMP.em

        if kernel_type is None:
           kernel_type=IMP.em.GAUSSIAN

        from math import sqrt

        self.representation_is_modified=True
        out_hier=[]
        protein_h=self.hier_dict[name]

        if "Densities" not in self.hier_representation[name]:
           root=IMP.atom.Hierarchy.setup_particle(IMP.Particle(self.m))
           root.set_name("Densities")
           self.hier_representation[name]["Densities"]=root
           protein_h.add_child(root)

        if inputfile is None:
           if particles is None:
              fragment_particles=[]
           else:
              fragment_particles=particles

           if not hierarchies is None:
              fragment_particles+=IMP.pmi.tools.select(self,resolution=resolution,
                                                       hierarchies=hierarchies)
           if not selection_tuples is None:
              for st in selection_tuples:
                 fragment_particles+=IMP.pmi.tools.select_by_tuple(self,tupleselection=st,
                                                                     resolution=resolution,
                                                                     name_is_ambiguous=False)
           if len(fragment_particles)==0:
              print "add_component_density: no particle was selected"
              return out_hier

           # compute mass
           mass_multiplier=1.0
           if multiply_by_total_mass:
               mass_multiplier=sum((IMP.atom.Mass(p).get_mass() for p in set(fragment_particles)))
               print 'add_component_density: will multiply by mass',mass_multiplier

           # simulate density from ps, then calculate points to fit
           print 'add_component_density: sampling points'
           dmap=IMP.em.SampledDensityMap(fragment_particles,1.0,voxel_size,
                                         IMP.atom.Mass.get_mass_key(),3,kernel_type)
           dmap.calcRMS()
           if not intermediate_map_fn is None:
               IMP.em.write_map(dmap,intermediate_map_fn)
           pts=IMP.isd_emxl.sample_points_from_density(dmap,sampled_points)

           # fit GMM
           density_particles=[]
           print 'add_component_density: fitting GMM'
           IMP.isd_emxl.gmm_tools.fit_gmm_to_points(pts,num_components,self.m,
                                                    density_particles,
                                                    num_iter,covariance_type,
                                                    mass_multiplier=mass_multiplier)

           if not outputfile is None:
               IMP.isd_emxl.gmm_tools.write_gmm_to_text(density_particles,outputfile)
           if not outputmap is None:
               IMP.isd_emxl.gmm_tools.write_gmm_to_map(density_particles,outputmap,
                                                       voxel_size,
                                                       IMP.em.get_bounding_box(dmap))

        else:
            # read the inputfile here
            density_particles=[]
            IMP.isd_emxl.gmm_tools.decorate_gmm_from_text(inputfile,density_particles,
                                                          self.m,transform)

        # prepare output hierarchy
        s0=IMP.atom.Fragment.setup_particle(IMP.Particle(self.m))
        s0.set_name(out_hier_name)
        self.hier_representation[name]["Densities"].add_child(s0)
        out_hier.append(s0)
        for nps,p in enumerate(density_particles):
            s0.add_child(p)
            p.set_name(s0.get_name()+'_gaussian_%i'%nps)
        return out_hier

    def get_component_density(self,name):
        return self.hier_representation[name]["Densities"]

    def add_all_atom_densities(self,name,hierarchies=None,
                               selection_tuples=None,
                               particles=None,
                               resolution=0.0,
                               output_map=None,
                               voxel_size=1.0):
        '''This function decorates all specified particles as Gaussians directly.
        name:                   component name
        hierarchies:            set up GMM for some hierarchies
        selection_tuples:       (list of tuples) example (first_residue,last_residue,component_name)
        particles:              set up GMM for particles directly
        resolution:             usual PMI resolution for selecting particles from the hierarchies
        intermediate_map_fn:    for debugging, this will write the itermediate (simulated) map
        '''

        import IMP.isd_emxl
        import IMP.isd_emxl.gmm_tools
        import IMP.em
        import numpy as np
        import sys
        from math import sqrt
        self.representation_is_modified=True

        if particles is None:
            fragment_particles=[]
        else:
            fragment_particles=particles

        if not hierarchies is None:
            fragment_particles+=IMP.pmi.tools.select(self,resolution=resolution,
                                                     hierarchies=hierarchies)

        if not selection_tuples is None:
            for st in selection_tuples:
                fragment_particles+=IMP.pmi.tools.select_by_tuple(self,tupleselection=st,
                                                                  resolution=resolution,
                                                                  name_is_ambiguous=False)

        if len(fragment_particles)==0:
            print "add_component_density: no particle was selected"
            return

        # create a sphereical gaussian for each particle based on atom type
        print 'setting up all atom gaussians num_particles',len(fragment_particles)
        for p in fragment_particles:
            center=IMP.core.XYZ(p).get_coordinates()
            rad=IMP.core.XYZR(p).get_radius()
            mass=IMP.atom.Mass(p).get_mass()
            trans=IMP.algebra.Transformation3D(IMP.algebra.get_identity_rotation_3d(),center)
            shape=IMP.algebra.Gaussian3D(IMP.algebra.ReferenceFrame3D(trans),[rad]*3)
            IMP.core.Gaussian.setup_particle(p,shape)
        if not output_map is None:
            print 'writing map to',output_map
            IMP.isd_emxl.gmm_tools.write_gmm_to_map(fragment_particles,output_map,voxel_size)



    def add_component_hierarchy_clone(self,name,hierarchy):
        '''
        this function makes a copy of a hierarchy and append it to a
        component
        '''
        outhier=[]
        self.representation_is_modified=True
        protein_h=self.hier_dict[name]
        hierclone=IMP.atom.create_clone(hierarchy)
        hierclone.set_name(hierclone.get_name()+"_clone")
        protein_h.add_child(hierclone)
        outhier.append(hierclone)

        psmain=IMP.atom.get_leaves(hierarchy)
        psclone=IMP.atom.get_leaves(hierclone)

        #copying attributes
        for n,pmain in enumerate(psmain):
           pclone=psclone[n]
           if IMP.pmi.Resolution.particle_is_instance(pmain):
              resolution=IMP.pmi.Resolution(pmain).get_resolution()
              IMP.pmi.Resolution.setup_particle(pclone,resolution)
              for kk in IMP.pmi.tools.get_residue_indexes(pclone):
                 self.hier_db.add_particles(name,kk,IMP.pmi.Resolution(pclone).get_resolution(),[pclone])

           if IMP.pmi.Uncertainty.particle_is_instance(pmain):
              uncertainty=IMP.pmi.Uncertainty(pmain).get_uncertainty()
              IMP.pmi.Uncertainty.setup_particle(pclone,uncertainty)

           if IMP.pmi.Symmetric.particle_is_instance(pmain):
              symmetric=IMP.pmi.Symmetric(pmain).get_symmetric()
              IMP.pmi.Symmetric.setup_particle(pclone,symmetric)

        return outhier

    def set_coordinates_from_rmf(self,component_name,rmf_file_name,rmf_frame_number,rmf_component_name=None):
        '''This function read and replace coordinates from an rmf file
        It looks for the component with the same name, unless the rmf_component_name
        is defined. Replace the coordinates of particles with the same name
        It assumes that the rmf and the represdentation have the particles in the same order'''

        import IMP.pmi.analysis

        prot=IMP.pmi.analysis.get_hier_from_rmf(self.m,rmf_frame_number,rmf_file_name)

        if not prot:

           print "set_coordinates_from_rmf: cannot read hiearchy from rmf"
           exit()
        #if len(self.rigid_bodies)!=0:
        #   print "set_coordinates_from_rmf: cannot proceed if rigid bodies were initialized. Use the function before defining the rigid bodies"
        #   exit()
        
        allpsrmf=IMP.atom.get_leaves(prot)
        
        psrmf=[]
        for p in allpsrmf:
           (protname,is_a_bead)=IMP.pmi.tools.get_prot_name_from_particle(p,self.hier_dict.keys())
           if not rmf_component_name is None and protname==rmf_component_name:
              psrmf.append(p)
           elif rmf_component_name is None and protname==component_name:
              psrmf.append(p)


        psrepr=IMP.atom.get_leaves(self.hier_dict[component_name])
        
       
        
        if len(psrmf) != len(psrepr):
           print "set_coordinates_from_rmf: cannot proceed the rmf and the representation don't have the same number of particles"
           print "particles in rmf: %s particles in the representation: %s" % (str(len(psrmf)),str(len(psrepr)))
           exit()           
        
        for n,prmf in enumerate(psrmf):
            prmfname=prmf.get_name()
            preprname=psrepr[n].get_name()
            if IMP.core.RigidMember.get_is_setup(psrepr[n]):
               print "set_coordinates_from_rmf: component %s cannot proceed if rigid bodies were initialized. Use the function before defining the rigid bodies" % component_name
               exit()
            if IMP.core.NonRigidMember.get_is_setup(psrepr[n]):
               print "set_coordinates_from_rmf: component %s cannot proceed if rigid bodies were initialized. Use the function before defining the rigid bodies" % component_name
               exit()
            
            if prmfname!=preprname:
               print "set_coordinates_from_rmf: WARNING rmf particle and representation particles have not the same name %s %s " % (prmfname,preprname)
            if IMP.core.XYZ.get_is_setup(prmf) and IMP.core.XYZ.get_is_setup(psrepr[n]):
               xyz=IMP.core.XYZ(prmf).get_coordinates()
               IMP.core.XYZ(psrepr[n]).set_coordinates(xyz)
            else:
               print "set_coordinates_from_rmf: WARNING particles are not XYZ decorated %s %s " % (str(IMP.core.XYZ.get_is_setup(prmf)) , str(IMP.core.XYZ.get_is_setup(psrepr[n])))
       
    def check_root(self,name,protein_h,resolution):
        '''
        checks whether the root hierarchy exists, and if not
        suitably constructs it
        '''
        if "Res:"+str(int(resolution)) not in self.hier_representation[name]:
           root=IMP.atom.Hierarchy.setup_particle(IMP.Particle(self.m))
           root.set_name(name+"_Res:"+str(int(resolution)))
           self.hier_representation[name]["Res:"+str(int(resolution))]=root
           protein_h.add_child(root)

    def coarse_hierarchy(self,name,start,end,resolutions,isnucleicacid,input_hierarchy,protein_h,type,color):
        '''
        this function generates all needed coarse grained layers
        name is the name of the protein
        resolutions is the list of resolutions
        protein_h is the root hierarchy
        input hierarchy is the hierarchy to coarse grain
        type is a string, typically "pdb" or "helix"
        '''
        outhiers=[]

        if (1 in resolutions) or (0 in resolutions):
           #in that case create residues and append atoms

           if 1 in resolutions:
              self.check_root(name,protein_h,1)
              s1=IMP.atom.Fragment.setup_particle(IMP.Particle(self.m))
              s1.set_name('%s_%i-%i_%s' % (name,start,end,type))
              self.hier_representation[name]["Res:1"].add_child(s1)
              outhiers+=[s1]
           if 0 in resolutions:
              self.check_root(name,protein_h,0)
              s0=IMP.atom.Fragment.setup_particle(IMP.Particle(self.m))
              s0.set_name('%s_%i-%i_%s' % (name,start,end,type))
              self.hier_representation[name]["Res:0"].add_child(s0)
              outhiers+=[s0]

           if not isnucleicacid:
              sel=IMP.atom.Selection(input_hierarchy,atom_type=IMP.atom.AT_CA)
           else:
              sel=IMP.atom.Selection(input_hierarchy,atom_type=IMP.atom.AT_P)

           for p in sel.get_selected_particles():
              resobject=IMP.atom.Residue(IMP.atom.Atom(p).get_parent())
              if 0 in resolutions:
                 #if you ask for atoms
                 resclone0=IMP.atom.create_clone(resobject)
                 resindex=IMP.atom.Residue(resclone0).get_index()
                 s0.add_child(resclone0)
                 self.hier_db.add_particles(name,resindex,0,resclone0.get_children())

                 chil=resclone0.get_children()
                 for ch in chil:
                   IMP.pmi.Resolution.setup_particle(ch,0)
                   try:
                     clr=IMP.display.get_rgb_color(color)
                   except:
                     clr=IMP.display.get_rgb_color(1.0)
                   IMP.display.Colored.setup_particle(ch,clr)


              if 1 in resolutions:
                 #else clone the residue
                 resclone1=IMP.atom.create_clone_one(resobject)
                 resindex=IMP.atom.Residue(resclone1).get_index()
                 s1.add_child(resclone1)
                 self.hier_db.add_particles(name,resindex,1,[resclone1])

                 rt=IMP.atom.Residue(resclone1).get_residue_type()
                 xyz=IMP.core.XYZ(p).get_coordinates()
                 prt=resclone1.get_particle()
                 prt.set_name('%s_%i_%s' % (name,resindex,type))
                 IMP.core.XYZ.setup_particle(prt).set_coordinates(xyz)

                 try:
                   vol=IMP.atom.get_volume_from_residue_type(rt)
                   #mass=IMP.atom.get_mass_from_residue_type(rt)
                 except IMP.base.ValueException:
                   vol=IMP.atom.get_volume_from_residue_type(IMP.atom.ResidueType("ALA"))
                   #mass=IMP.atom.get_mass_from_residue_type(IMP.atom.ResidueType("ALA"))
                 radius=IMP.algebra.get_ball_radius_from_volume_3d(vol)
                 IMP.core.XYZR.setup_particle(prt).set_radius(radius)
                 IMP.atom.Mass.setup_particle(prt,100)
                 IMP.pmi.Uncertainty.setup_particle(prt,radius)
                 IMP.pmi.Symmetric.setup_particle(prt,0)
                 IMP.pmi.Resolution.setup_particle(prt,1)
                 try:
                   clr=IMP.display.get_rgb_color(color)
                 except:
                   clr=IMP.display.get_rgb_color(1.0)
                 IMP.display.Colored.setup_particle(prt,clr)

        for r in resolutions:
          if r!=0 and r!=1:
            self.check_root(name,protein_h,r)
            s=IMP.atom.create_simplified_along_backbone(input_hierarchy, r)

            chil=s.get_children()
            s0=IMP.atom.Fragment.setup_particle(IMP.Particle(self.m))
            s0.set_name('%s_%i-%i_%s' % (name,start,end,type))
            for ch in chil: s0.add_child(ch)
            self.hier_representation[name]["Res:"+str(int(r))].add_child(s0)
            outhiers+=[s0]
            del s

            for prt in IMP.atom.get_leaves(s0):
                ri=IMP.atom.Fragment(prt).get_residue_indexes()
                first=ri[0]
                last=ri[-1]
                if first==last:
                   prt.set_name('%s_%i_%s' % (name,first,type))
                else:
                   prt.set_name('%s_%i_%i_%s' % (name,first,last,type))
                for kk in ri:
                   self.hier_db.add_particles(name,kk,r,[prt])

                radius=IMP.core.XYZR(prt).get_radius()
                IMP.pmi.Uncertainty.setup_particle(prt,radius)
                IMP.pmi.Symmetric.setup_particle(prt,0)
                IMP.pmi.Resolution.setup_particle(prt,r)

                #setting up color for each particle in the
                #hierarchy, if colors missing in the colors list set it to red
                try:
                    clr=IMP.display.get_rgb_color(color)
                except:
                    colors.append(1.0)
                    clr=IMP.display.get_rgb_color(colors[pdb_part_count])
                IMP.display.Colored.setup_particle(prt,clr)

        return outhiers

    def get_hierarchies_at_given_resolution(self,resolution):
        '''
        this function caches the map between resolution and hierarchies
        to accelerate the selection algorithm
        if the representation was changed by any add_component_xxx, the function recalculates
        the maps
        '''

        if self.representation_is_modified:
           rhbr=self.hier_db.get_all_root_hierarchies_by_resolution(resolution)
           self.hier_resolution[resolution]=rhbr
           self.representation_is_modified=False
           return rhbr
        else:
           if resolution in self.hier_resolution:
              return self.hier_resolution[resolution]
           else:
              rhbr=self.hier_db.get_all_root_hierarchies_by_resolution(resolution)
              self.hier_resolution[resolution]=rhbr
              return rhbr

    def shuffle_configuration(self,max_translation=300.,max_rotation=2.0*pi,
                              avoidcollision=True,cutoff=10.0,niterations=100,
                              bounding_box=None,
                              excluded_rigid_bodies=None,
                              hierarchies_excluded_from_collision=None):
        '''
        shuffle configuration, used to restart the optimization
        it  works correctly if rigid bodies were initialized
        avoidcollision check if the particle/rigid body was placed close to another particle
        avoidcollision uses the optional arguments cutoff and niterations

        bounding box is defined by ((x1,y1,z1),(x2,y2,z2))

        '''
        if excluded_rigid_bodies is None: excluded_rigid_bodies=[]
        if hierarchies_excluded_from_collision is None: hierarchies_excluded_from_collision=[]

        if len(self.rigid_bodies)==0:
            print "shuffle_configuration: rigid bodies were not intialized"

        gcpf=IMP.core.GridClosePairsFinder()
        gcpf.set_distance(cutoff)
        ps=[]
        for p in IMP.atom.get_leaves(self.prot):
            if IMP.core.XYZ.particle_is_instance(p):
               ps.append(p)
        allparticleindexes=IMP.get_indexes(ps)


        if not bounding_box is None:
           ((x1,y1,z1),(x2,y2,z2))=bounding_box
           ub=IMP.algebra.Vector3D(x1,y1,z1)
           lb=IMP.algebra.Vector3D(x2,y2,z2)
           bb=IMP.algebra.BoundingBox3D(ub,lb)


        hierarchies_excluded_from_collision_indexes=[]
        for h in hierarchies_excluded_from_collision:
            hierarchies_excluded_from_collision_indexes+=IMP.get_indexes(IMP.atom.get_leaves(h))

        # remove the densities particles out of the calculation
        for name in self.hier_representation:
          try:
            IMP.atom.get_leaves(self.hier_representation[name]["Densities"])
            hierarchies_excluded_from_collision_indexes+=IMP.get_indexes(ps)
          except:
            pass

        allparticleindexes=list(set(allparticleindexes)-set(hierarchies_excluded_from_collision_indexes))

        for rb in self.rigid_bodies:
          if rb not in excluded_rigid_bodies:
            if avoidcollision:

               rbindexes=rb.get_member_particle_indexes()

               rbindexes=list(set(rbindexes)-set(hierarchies_excluded_from_collision_indexes))
               otherparticleindexes=list(set(allparticleindexes)-set(rbindexes))
               if len(otherparticleindexes) is None: continue

            niter=0
            while niter<niterations:
               rbxyz=(rb.get_x(), rb.get_y(), rb.get_z())

               if not bounding_box is None:
                  #overrides the perturbation
                  translation=IMP.algebra.get_random_vector_in(bb)
                  rotation=IMP.algebra.get_random_rotation_3d()
                  transformation=IMP.algebra.Transformation3D(rotation,translation)
               else:
                  transformation=IMP.algebra.get_random_local_transformation(rbxyz,max_translation,max_rotation)

               IMP.core.transform(rb,transformation)

               if avoidcollision:
                  self.m.update()
                  npairs=len(gcpf.get_close_pairs(self.m,otherparticleindexes,rbindexes))
                  if npairs==0: niter=niterations
                  else:
                     niter+=1
                     print "shuffle_configuration: rigid body placed close to other %d particles, trying again..." % npairs
                     print "shuffle_configuration: rigid body name: "+rb.get_name()
                     if niter==niterations:
                        print "shuffle_configuration: tried the maximum number of iterations to avoid collisions, increase the distance cutoff"
                        exit()
               else:
                  break

        print 'shuffling',len(self.floppy_bodies),'floppy bodies'
        for fb in self.floppy_bodies:
            if avoidcollision:
               rm=not IMP.core.RigidMember.get_is_setup(fb)
               nrm=not IMP.core.NonRigidMember.get_is_setup(fb)
               if rm and nrm:
                  fbindexes=IMP.get_indexes([fb])
                  otherparticleindexes=list(set(allparticleindexes)-set(fbindexes))
                  if len(otherparticleindexes) is None: continue
               else: continue

            niter=0
            while niter<niterations:
               fbxyz=IMP.core.XYZ(fb).get_coordinates()
               if not bounding_box is None:
                  #overrides the perturbation
                  translation=IMP.algebra.get_random_vector_in(bb)
                  transformation=IMP.algebra.Transformation3D(translation)
               else:
                  transformation=IMP.algebra.get_random_local_transformation(fbxyz,max_translation,max_rotation)

               IMP.core.transform(IMP.core.XYZ(fb),transformation)

               if avoidcollision:
                  self.m.update()
                  npairs=len(gcpf.get_close_pairs(self.m,otherparticleindexes,fbindexes))
                  if npairs==0: niter=niterations
                  else:
                     niter+=1
                     print "shuffle_configuration: floppy body placed close to other %d particles, trying again..." % npairs
                     if niter==niterations:
                        print "shuffle_configuration: tried the maximum number of iterations to avoid collisions, increase the distance cutoff"
                        exit()
               else:
                  break



    def set_current_coordinates_as_reference_for_rmsd(self,label="None"):
        # getting only coordinates from pdb
        ps=IMP.pmi.tools.select(self,resolution=1.0)
        # storing the reference coordinates and the particles
        self.reference_structures[label]=([IMP.core.XYZ(p).get_coordinates() for p in ps],ps)

    def get_all_rmsds(self):
        rmsds={}

        for label in self.reference_structures:

            current_coordinates=[IMP.core.XYZ(p).get_coordinates() for p in self.reference_structures[label][1]]
            reference_coordinates=self.reference_structures[label][0]
            if len(reference_coordinates)!=len(current_coordinates):
               print "calculate_all_rmsds: reference and actual coordinates are not the same"
               continue
            transformation=IMP.algebra.get_transformation_aligning_first_to_second(current_coordinates, reference_coordinates)
            rmsd_global=IMP.algebra.get_rmsd(reference_coordinates,current_coordinates)
            #warning: temporary we are calculating the drms, and not the rmsd, for the relative distance
            rmsd_relative=IMP.atom.get_drms(reference_coordinates,current_coordinates)
            rmsds[label+"_GlobalRMSD"]=rmsd_global
            rmsds[label+"_RelativeDRMS"]=rmsd_relative
        return rmsds

    def setup_component_geometry(self,name,color=None,resolution=1.0):
        if color is None:
           color=self.color_dict[name]
        #this function stores all particle pairs
        #ordered by residue number, to be used
        #to construct backbone traces
        self.hier_geometry_pairs[name]=[]
        protein_h=self.hier_dict[name]
        pbr=IMP.pmi.tools.select(self,name=name,resolution=resolution)
        pbr=IMP.pmi.tools.sort_by_residues(pbr)

        for n in range(len(pbr)-1):
            self.hier_geometry_pairs[name].append((pbr[n],pbr[n+1],color))

    def setup_component_sequence_connectivity(self,name,resolution=10,scale=1.0):
        '''
        This method generates restraints between contiguous fragments
        in the hierarchy. The linkers are generated at resolution 10 by default.

        '''

        unmodeledregions_cr=IMP.RestraintSet(self.m,"unmodeledregions")
        sortedsegments_cr=IMP.RestraintSet(self.m,"sortedsegments")

        protein_h=self.hier_dict[name]
        SortedSegments = []
        frs=self.hier_db.get_preroot_fragments_by_resolution(name,resolution)

        for fr in frs:
            try:
               start = fr.get_children()[0]
            except:
               start = fr

            try:
               end   = fr.get_children()[-1]
            except:
               end   = fr

            startres = IMP.pmi.tools.get_residue_indexes(start)[0]
            endres   = IMP.pmi.tools.get_residue_indexes(end)[-1]
            SortedSegments.append((start,end,startres))
        SortedSegments = sorted(SortedSegments, key=itemgetter(2))

        #connect the particles
        for x in xrange(len(SortedSegments)-1):
            last = SortedSegments[x][1]
            first= SortedSegments[x+1][0]

            nreslast=len(IMP.pmi.tools.get_residue_indexes(last))
            lastresn=IMP.pmi.tools.get_residue_indexes(last)[-1]
            nresfirst=len(IMP.pmi.tools.get_residue_indexes(first))
            firstresn=IMP.pmi.tools.get_residue_indexes(first)[0]

            residuegap=firstresn-lastresn-1

            if self.disorderedlength and (nreslast/2+nresfirst/2+residuegap)>20.0 :
               #calculate the distance between the sphere centers using Kohn PNAS 2004
               optdist=sqrt(5/3)*1.93*(nreslast/2+nresfirst/2+residuegap)**0.6
               #optdist2=sqrt(5/3)*1.93*((nreslast)**0.6+(nresfirst)**0.6)/2
               if self.upperharmonic:
                  hu=IMP.core.HarmonicUpperBound(optdist, self.kappa)
               else:
                  hu=IMP.core.Harmonic(optdist, self.kappa)
               dps=IMP.core.DistancePairScore(hu)
            else: #default
               optdist=(0.0+(float(residuegap)+1.0)*3.6)*scale
               if self.upperharmonic: #default
                  hu=IMP.core.HarmonicUpperBound(optdist, self.kappa)
               else:
                  hu=IMP.core.Harmonic(optdist, self.kappa)
               dps=IMP.core.SphereDistancePairScore(hu)

            pt0=last.get_particle()
            pt1=first.get_particle()
            r=IMP.core.PairRestraint(dps,IMP.ParticlePair(pt0,pt1))

            print "Adding sequence connectivity restraint between", pt0.get_name(), " and ", pt1.get_name()
            sortedsegments_cr.add_restraint(r)
            self.linker_restraints_dict["LinkerRestraint-"+pt0.get_name()+"-"+pt1.get_name()]=r
            self.connected_intra_pairs.append((pt0,pt1))
            self.connected_intra_pairs.append((pt1,pt0))

        self.m.add_restraint(sortedsegments_cr)
        self.m.add_restraint(unmodeledregions_cr)
        self.linker_restraints.add_restraint(sortedsegments_cr)
        self.linker_restraints.add_restraint(unmodeledregions_cr)
        self.sortedsegments_cr_dict[name]=sortedsegments_cr
        self.unmodeledregions_cr_dict[name]=unmodeledregions_cr

    def optimize_floppy_bodies(self,nsteps,temperature=1.0):
        import IMP.pmi.samplers
        pts=IMP.pmi.tools.ParticleToSampleList()
        for n,fb in enumerate(self.floppy_bodies):
            pts.add_particle(fb,"Floppy_Bodies",1.0,"Floppy_Body_"+str(n))
        if len(pts.get_particles_to_sample())>0:
           mc = IMP.pmi.samplers.MonteCarlo(self.m,[pts], temperature)
           print "optimize_floppy_bodies: optimizing %i floppy bodies" % len(self.floppy_bodies)
           mc.optimize(nsteps)
        else:
           print "optimize_floppy_bodies: no particle to optimize"

    def create_rotational_symmetry(self,maincopy,copies):
        from math import pi
        self.representation_is_modified=True
        ncopies=len(copies)+1

        sel=IMP.atom.Selection(self.prot,molecule=maincopy)
        mainparticles=sel.get_selected_particles()

        for k in range(len(copies)):
          rotation3D=IMP.algebra.get_rotation_about_axis(IMP.algebra.Vector3D(0,0,1), 2*pi/ncopies*(k+1))
          sm=IMP.core.TransformationSymmetry(rotation3D)


          sel=IMP.atom.Selection(self.prot,molecule=copies[k])
          copyparticles=sel.get_selected_particles()

          mainpurged=[]
          copypurged=[]
          for n,p in enumerate(mainparticles):

            pc=copyparticles[n]

            mainpurged.append(p)
            IMP.pmi.Symmetric.setup_particle(p,0)

            copypurged.append(pc)
            IMP.pmi.Symmetric.setup_particle(pc,1)

          lc=IMP.container.ListSingletonContainer(self.m)
          for n,p in enumerate(mainpurged):

            pc=copypurged[n]
            print "setting "+p.get_name()+" as reference for "+pc.get_name()


            IMP.core.Reference.setup_particle(pc,p)
            lc.add_particle(pc)

          c=IMP.container.SingletonsConstraint(sm,None,lc)
          self.m.add_score_state(c)

        self.m.update()

    def create_amyloid_fibril_symmetry(self,maincopy,axial_copies,
                longitudinal_copies,axis=(0,0,1),translation_value=4.8):

        from math import pi
        self.representation_is_modified=True

        outhiers=[]
        protein_h=self.hier_dict[maincopy]
        mainparts=IMP.atom.get_leaves(protein_h)

        for ilc in range(-longitudinal_copies,longitudinal_copies+1):
            for iac in range(axial_copies):
                copyname=maincopy+"_a"+str(ilc)+"_l"+str(iac)
                self.add_component_name(copyname,0.0)
                for hier in protein_h.get_children():
                    self.add_component_hierarchy_clone(copyname,hier)
                copyhier=self.hier_dict[copyname]
                outhiers.append(copyhier)
                copyparts=IMP.atom.get_leaves(copyhier)
                rotation3D=IMP.algebra.get_rotation_about_axis(IMP.algebra.Vector3D(axis), 2*pi/axial_copies*(float(iac)))
                translation_vector=tuple([translation_value*float(ilc)*x for x in axis])
                print translation_vector
                translation=IMP.algebra.Vector3D(translation_vector)
                sm=IMP.core.TransformationSymmetry(IMP.algebra.Transformation3D(rotation3D,translation))
                lc=IMP.container.ListSingletonContainer(self.m)
                for n,p in enumerate(mainparts):
                    pc=copyparts[n]
                    if not IMP.pmi.Symmetric.particle_is_instance(p):
                       IMP.pmi.Symmetric.setup_particle(p,0)
                    if not IMP.pmi.Symmetric.particle_is_instance(pc):
                       IMP.pmi.Symmetric.setup_particle(pc,1)
                    IMP.core.Reference.setup_particle(pc,p)
                    lc.add_particle(pc)
                c=IMP.container.SingletonsConstraint(sm,None,lc)
                self.m.add_score_state(c)
                self.m.update()
        return outhiers

    def link_components_to_rmf(self,rmfname,frameindex):
        '''
        load coordinates in the current representation
        this should be done only if the hierarchy self.prot is identical to the one
        i.e. all components were added
        as stored in the rmf
        '''
        import IMP.rmf
        import RMF
        
        rh= RMF.open_rmf_file_read_only(rmfname)
        IMP.rmf.link_hierarchies(rh, [self.prot])
        IMP.rmf.load_frame(rh, frameindex)
        del rh

    def create_components_from_rmf(self,rmfname,frameindex):
        '''
        still not working.
        create the representation (i.e. hierarchies) from the rmf file.
        it will be stored in self.prot, which will be overwritten.
        load the coordinates from the rmf file at frameindex.
        '''
        rh= RMF.open_rmf_file(rmfname)
        self.prot=IMP.rmf.create_hierarchies(rh, self.m)[0]
        IMP.atom.show_molecular_hierarchy(self.prot)
        IMP.rmf.link_hierarchies(rh, [self.prot])
        IMP.rmf.load_frame(rh, frameindex)
        del rh
        for p in self.prot.get_children():
            self.add_component_name(p.get_name())
            self.hier_dict[p.get_name()]=p
        '''
        still missing: save rigid bodies contained in the rmf in self.rigid_bodies
        save floppy bodies in self.floppy_bodies
        get the connectivity restraints
        '''

    def set_rigid_body_from_hierarchies(self,hiers,particles=None):
        '''
        This method allows the construction of a rigid body given a list
        of hierarchies and or a list of particles.

        hiers:         list of hierarchies
        particles:     (optional, default=None) list of particles to add to the rigid body
        '''

        if particles is None:
           rigid_parts=set()
        else:
           rigid_parts=set(particles)

        name=""
        print "set_rigid_body_from_hierarchies> setting up a new rigid body"
        for hier in hiers:
            ps=IMP.atom.get_leaves(hier)
            for p in ps:
              if IMP.core.RigidMember.particle_is_instance(p):
                 rb=IMP.core.RigidMember(p).get_rigid_body()
                 print "set_rigid_body_from_hierarchies> WARNING particle %s already belongs to rigid body %s" % (p.get_name(),rb.get_name())
              else:
                 rigid_parts.add(p)
            name+=hier.get_name()+"-"
            print "set_rigid_body_from_hierarchies> adding %s to the rigid body" % hier.get_name()
        rb=IMP.atom.create_rigid_body(list(rigid_parts))
        rb.set_coordinates_are_optimized(True)
        rb.set_name(name+"rigid_body")
        self.rigid_bodies.append(rb)
        return rb

    def set_rigid_bodies(self,subunits):
        '''
        This method allows the construction of a rigid body given a list
        of tuples, that identify the residue ranges and the subunit names (the names used
        to create the component by using create_component.

        subunits: [(name_1,(first_residue_1,last_residue_1)),(name_2,(first_residue_2,last_residue_2)),.....]
                  or
                  [name_1,name_2,(name_3,(first_residue_3,last_residue_3)),.....]

                   example: ["prot1","prot2",("prot3",(1,10))]

        sometimes, we know about structure of an interaction
        and here we make such PPIs rigid
        '''

        rigid_parts=set()
        for s in subunits:
            if type(s)==type(tuple()) and len(s)==2:
               sel=IMP.atom.Selection(self.prot,molecule=s[0],residue_indexes=range(s[1][0],s[1][1]+1))
               if len(sel.get_selected_particles())==0:
                  print "set_rigid_bodies: selected particle does not exists"
               for p in sel.get_selected_particles():
                  #if not p in self.floppy_bodies:
                      if IMP.core.RigidMember.particle_is_instance(p):
                         rb=IMP.core.RigidMember(p).get_rigid_body()
                         print "set_rigid_body_from_hierarchies> WARNING particle %s already belongs to rigid body %s" % (p.get_name(),rb.get_name())
                      else:
                         rigid_parts.add(p)


            elif type(s)==type(str()):
               sel=IMP.atom.Selection(self.prot,molecule=s)
               if len(sel.get_selected_particles())==0:
                  print "set_rigid_bodies: selected particle does not exists"
               for p in sel.get_selected_particles():
                  #if not p in self.floppy_bodies:
                      if IMP.core.RigidMember.particle_is_instance(p):
                         rb=IMP.core.RigidMember(p).get_rigid_body()
                         print "set_rigid_body_from_hierarchies> WARNING particle %s already belongs to rigid body %s" % (p.get_name(),rb.get_name())
                      else:
                         rigid_parts.add(p)

        rb=IMP.atom.create_rigid_body(list(rigid_parts))
        rb.set_coordinates_are_optimized(True)
        rb.set_name(''.join(str(subunits))+"_rigid_body")
        self.rigid_bodies.append(rb)
        return rb

    def set_super_rigid_body_from_hierarchies(self,hiers,axis=None,min_size=0):
        #axis is the rotation axis for 2D rotation
        super_rigid_xyzs=set()
        super_rigid_rbs=set()
        name=""
        print "set_super_rigid_body_from_hierarchies> setting up a new SUPER rigid body"

        for hier in hiers:
            ps=IMP.atom.get_leaves(hier)
            for p in ps:
              if IMP.core.RigidMember.particle_is_instance(p):
                 rb=IMP.core.RigidMember(p).get_rigid_body()
                 super_rigid_rbs.add(rb)
              else:
                 super_rigid_xyzs.add(p)
            print "set_rigid_body_from_hierarchies> adding %s to the rigid body" % hier.get_name()
        if len(super_rigid_rbs)<min_size:
            return
        if axis is None:
           self.super_rigid_bodies.append((super_rigid_xyzs,super_rigid_rbs))
        else:
           #these will be 2D rotation SRB
           self.super_rigid_bodies.append((super_rigid_xyzs,super_rigid_rbs,axis))
    def fix_rigid_bodies(self,rigid_bodies):
        self.fixed_rigid_bodies+=rigid_bodies


    def set_chain_of_super_rigid_bodies(self,hiers,min_length=None,max_length=None,axis=None):
        '''
        this function takes a linear list of hierarchies (they are supposed
         to be sequence-contiguous) and
        produces a chain of super rigid bodies with given length range, specified
        by min_length and max_length
        '''
        try:
          hiers=IMP.pmi.tools.flatten_list(hiers)
        except:
            pass
        for hs in IMP.pmi.tools.sublist_iterator(hiers,min_length,max_length):
            self.set_super_rigid_body_from_hierarchies(hs,axis,min_length)

    def set_super_rigid_bodies(self,subunits,coords=None):
        super_rigid_xyzs=set()
        super_rigid_rbs=set()

        for s in subunits:
            if type(s)==type(tuple()) and len(s)==2:
               sel=IMP.atom.Selection(self.prot,molecule=s[0],residue_indexes=range(s[1][0],s[1][1]+1))
               if len(sel.get_selected_particles())==0:
                  print "set_rigid_bodies: selected particle does not exists"
               for p in sel.get_selected_particles():
                      if IMP.core.RigidMember.particle_is_instance(p):
                         rb=IMP.core.RigidMember(p).get_rigid_body()
                         super_rigid_rbs.add(rb)
                      else:
                         super_rigid_xyzs.add(p)
            elif type(s)==type(str()):
               sel=IMP.atom.Selection(self.prot,molecule=s)
               if len(sel.get_selected_particles())==0:
                  print "set_rigid_bodies: selected particle does not exists"
               for p in sel.get_selected_particles():
                  #if not p in self.floppy_bodies:
                      if IMP.core.RigidMember.particle_is_instance(p):
                         rb=IMP.core.RigidMember(p).get_rigid_body()
                         super_rigid_rbs.add(rb)
                      else:
                         super_rigid_xyzs.add(p)
        self.super_rigid_bodies.append((super_rigid_xyzs,super_rigid_rbs))

    def set_floppy_bodies(self):
        for p in self.floppy_bodies:
            name=p.get_name()
            p.set_name(name+"_floppy_body")
            if IMP.core.RigidMember.particle_is_instance(p):
                print "I'm trying to make this particle flexible although it was assigned to a rigid body", p.get_name()
                rb=IMP.core.RigidMember(p).get_rigid_body()
                try:
                   rb.set_is_rigid_member(p.get_index(),False)
                except:
                   # some IMP versions still work with that
                   rb.set_is_rigid_member(p.get_particle_index(),False)
                p.set_name(p.get_name()+"_rigid_body_member")

    def set_floppy_bodies_from_hierarchies(self,hiers):
        for hier in hiers:
            ps=IMP.atom.get_leaves(hier)
            for p in ps:
               IMP.core.XYZ(p).set_coordinates_are_optimized(True)
               self.floppy_bodies.append(p)

    def get_particles_from_selection_tuples(self,selection_tuples,resolution=None):
        '''
        selection tuples must be [(r1,r2,"name1"),(r1,r2,"name2"),....]
        return the particles
        '''
        particles=[]
        print selection_tuples
        for s in selection_tuples:
            ps=IMP.pmi.tools.select_by_tuple(representation=self,tupleselection=tuple(s),
                                          resolution=None,name_is_ambiguous=False)
            particles+=ps
        return particles

    def get_connected_intra_pairs(self):
        return self.connected_intra_pairs

    def set_rigid_bodies_max_trans(self,maxtrans):
        self.maxtrans_rb=maxtrans

    def set_rigid_bodies_max_rot(self,maxrot):
        self.maxrot_rb=maxrot

    def set_floppy_bodies_max_trans(self,maxtrans):
        self.maxtrans_fb=maxtrans

    def set_rigid_bodies_as_fixed(self,rigidbodiesarefixed=True):
        '''
        this function will fix rigid bodies in their actual
        position. the get_particles_to_sample function will return
        just the floppy bodies.
        '''
        self.rigidbodiesarefixed=rigidbodiesarefixed

    def draw_hierarchy_graph(self):
        for c in IMP.atom.Hierarchy(self.prot).get_children():
            print "Drawing hierarchy graph for "+c.get_name()
            IMP.pmi.output.get_graph_from_hierarchy(c)

    def get_geometries(self):
        #create segments at the lowest resolution
        seggeos=[]
        for name in self.hier_geometry_pairs:
            for pt in self.hier_geometry_pairs[name]:
                p1=pt[0]
                p2=pt[1]
                color=pt[2]
                try:
                    clr=IMP.display.get_rgb_color(color)
                except:
                    clr=IMP.display.get_rgb_color(1.0)
                coor1=IMP.core.XYZ(p1).get_coordinates()
                coor2=IMP.core.XYZ(p2).get_coordinates()
                seg=IMP.algebra.Segment3D(coor1,coor2)
                seggeos.append(IMP.display.SegmentGeometry(seg,clr))
        return seggeos

    def setup_bonds(self):
        #create segments at the lowest resolution
        seggeos=[]
        for name in self.hier_geometry_pairs:
            for pt in self.hier_geometry_pairs[name]:

                p1=pt[0]
                p2=pt[1]
                if not IMP.atom.Bonded.particle_is_instance(p1):
                   IMP.atom.Bonded.setup_particle(p1)
                if not IMP.atom.Bonded.particle_is_instance(p2):
                   IMP.atom.Bonded.setup_particle(p2)

                IMP.atom.create_bond(IMP.atom.Bonded(p1),IMP.atom.Bonded(p2),1)

    def show_component_table(self,name):
        if name in self.sequence_dict:
           lastresn=len(self.sequence_dict[name])
           firstresn=1
        else:
           residues=self.hier_db.get_residue_numbers(name)
           firstresn=min(residues)
           lastresn=max(residues)

        for nres in range(firstresn,lastresn+1):
            try:
               resolutions=self.hier_db.get_residue_resolutions(name,nres)
               ps=[]
               for r in resolutions:
                  ps+=self.hier_db.get_particles(name,nres,r)
               print "%20s %7s" % (name,nres), " ".join(["%20s %7s" % (str(p.get_name()),
                     str(IMP.pmi.Resolution(p).get_resolution())) for p in ps])
            except:
               print "%20s %20s" % (name,nres), "**** not represented ****"

    def draw_hierarchy_composition(self):

        ks=self.elements.keys()
        ks.sort()

        max=0
        for k in self.elements:
            for l in self.elements[k]:
                if l[1]>max: max=l[1]

        for k in ks:
            self.draw_component_composition(k,max)

    def draw_component_composition(self,name,max=1000):
            from matplotlib import pyplot
            import matplotlib as mpl
            k=name
            list=sorted(self.elements[k], key=itemgetter(0))
            endres=list[-1][1]
            fig = pyplot.figure(figsize=(26.0*float(endres)/max+2,2))
            ax = fig.add_axes([0.05, 0.475, 0.9, 0.15])

            # Set the colormap and norm to correspond to the data for which
            # the colorbar will be used.
            cmap = mpl.cm.cool
            norm = mpl.colors.Normalize(vmin=5, vmax=10)
            bounds=[1]
            colors=[]

            for n,l in enumerate(list):
                firstres=l[0]
                lastres=l[1]
                if l[3]!="end":
                    if bounds[-1]!=l[0]:
                       colors.append("white")
                       bounds.append(l[0])
                       if l[3]=="pdb": colors.append("#99CCFF")
                       if l[3]=="bead": colors.append("#FFFF99")
                       if l[3]=="helix": colors.append("#33CCCC")
                       if l[3]!="end":
                          bounds.append(l[1]+1)
                    else:
                       if l[3]=="pdb": colors.append("#99CCFF")
                       if l[3]=="bead": colors.append("#FFFF99")
                       if l[3]=="helix": colors.append("#33CCCC")
                       if l[3]!="end":
                          bounds.append(l[1]+1)
                else:
                   if bounds[-1]-1==l[0]:
                      bounds.pop()
                      bounds.append(l[0])
                   else:
                      colors.append("white")
                      bounds.append(l[0])

            bounds.append(bounds[-1])
            colors.append("white")
            cmap = mpl.colors.ListedColormap(colors)
            cmap.set_over('0.25')
            cmap.set_under('0.75')

            norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
            cb2 = mpl.colorbar.ColorbarBase(ax, cmap=cmap,
                                     norm=norm,
                                     # to use 'extend', you must
                                     # specify two extra boundaries:
                                     boundaries=bounds,
                                     ticks=bounds, # optional
                                     spacing='proportional',
                                     orientation='horizontal')

            extra_artists=[]
            npdb=0
            for l in list:
                if l[3]=="pdb":
                   npdb+=1
                   mid=1.0/endres*float(l[0])
                   #t =ax.text(mid, float(npdb-1)/2.0+1.5, l[2], ha="left", va="center", rotation=0,
                   #size=10)
                   #t=ax.annotate(l[0],2)
                   t=ax.annotate(l[2], xy=(mid, 1),  xycoords='axes fraction',
                   xytext=(mid+0.025, float(npdb-1)/2.0+1.5), textcoords='axes fraction',
                   arrowprops=dict(arrowstyle="->",
                                connectionstyle="angle,angleA=0,angleB=90,rad=10"),
                   )
                   extra_artists.append(t)

            #set the title of the bar
            title=ax.text(-0.005, 0.5, k, ha="right", va="center", rotation=90,
                size=15)

            extra_artists.append(title)
            #changing the xticks labels
            labels=len(bounds)*[" "]
            ax.set_xticklabels(labels)
            mid=1.0/endres*float(bounds[0])
            t=ax.annotate(bounds[0], xy=(mid, 0),  xycoords='axes fraction',
                   xytext=(mid-0.01, -0.5), textcoords='axes fraction',)
            extra_artists.append(t)
            offsets=[0,-0.5,-1.0]
            nclashes=0
            for n in range(1,len(bounds)):
                if bounds[n]==bounds[n-1]: continue
                mid=1.0/endres*float(bounds[n])
                if (float(bounds[n])-float(bounds[n-1]))/max<=0.01:
                   nclashes+=1
                   offset=offsets[nclashes%3]
                else:
                   nclashes=0
                   offset=offsets[0]
                if offset>-0.75:
                  t=ax.annotate(bounds[n], xy=(mid, 0),  xycoords='axes fraction',
                     xytext=(mid, -0.5+offset), textcoords='axes fraction')
                else:
                  t=ax.annotate(bounds[n], xy=(mid, 0),  xycoords='axes fraction',
                     xytext=(mid, -0.5+offset), textcoords='axes fraction',arrowprops=dict(arrowstyle="-"))
                extra_artists.append(t)

            cb2.add_lines(bounds,["black"]*len(bounds),[1]*len(bounds))
            #cb2.set_label(k)

            pyplot.savefig(k+"structure.png",dpi=150,transparent="True",bbox_extra_artists=(extra_artists), bbox_inches='tight')
            pyplot.show()

    def draw_coordinates_projection(self):
        import matplotlib.pyplot as pp
        xpairs=[]
        ypairs=[]
        for name in self.hier_geometry_pairs:
            for pt in self.hier_geometry_pairs[name]:
                p1=pt[0]
                p2=pt[1]
                color=pt[2]
                coor1=IMP.core.XYZ(p1).get_coordinates()
                coor2=IMP.core.XYZ(p2).get_coordinates()
                x1=coor1[0];x2=coor2[0]
                y1=coor1[1];y2=coor2[1]
                xpairs.append([x1,x2])
                ypairs.append([y1,y2])
        xlist = []
        ylist = []
        for xends,yends in zip(xpairs,ypairs):
            xlist.extend(xends)
            xlist.append(None)
            ylist.extend(yends)
            ylist.append(None)
        pp.plot(xlist,ylist,'b-',alpha=0.1)
        pp.show()

    def get_prot_name_from_particle(self,particle):
            names=self.get_component_names()
            particle0=particle
            name=None
            while not name in names:
                 h=IMP.atom.Hierarchy(particle0).get_parent()
                 name=h.get_name()
                 particle0=h.get_particle()
            return name

    def get_random_residue_pairs(self,names,resolution,number):
            from random import choice
            particles=[]
            for name in names:
                prot=self.hier_dict[name]
                particles+=IMP.pmi.tools.get_particles_by_resolution(prot,resolution)

            random_residue_pairs=[]
            for i in range(number):
                p1=choice(particles)
                p2=choice(particles)
                r1=choice(IMP.pmi.tools.get_residue_indexes(p1))
                r2=choice(IMP.pmi.tools.get_residue_indexes(p2))
                name1=self.get_prot_name_from_particle(p1)
                name2=self.get_prot_name_from_particle(p2)
                random_residue_pairs.append((name1,r1,name2,r2))
            return random_residue_pairs

    def get_particles_to_sample(self):
        #get the list of samplable particles with their type
        #and the mover displacement. Everything wrapped in a dictionary,
        #to be used by samplers modules
        ps={}

        #remove symmetric particles: they are not sampled
        rbtmp=[]
        fbtmp=[]
        srbtmp=[]
        if not self.rigidbodiesarefixed:
            for rb in self.rigid_bodies:
               if IMP.pmi.Symmetric.particle_is_instance(rb):
                  if IMP.pmi.Symmetric(rb).get_symmetric()!=1:
                     rbtmp.append(rb)
               else:
                  if rb not in self.fixed_rigid_bodies:
                     rbtmp.append(rb)

        for fb in self.floppy_bodies:
           if IMP.pmi.Symmetric.particle_is_instance(fb):
              if IMP.pmi.Symmetric(fb).get_symmetric()!=1:
                 fbtmp.append(fb)
           else:
              fbtmp.append(fb)

        for srb in self.super_rigid_bodies:
            #going to prune the fixed rigid bodies out
            #of the super rigid body list
            rigid_bodies=list(srb[1])
            filtered_rigid_bodies=[]
            for rb in rigid_bodies:
                if rb not in self.fixed_rigid_bodies:
                   filtered_rigid_bodies.append(rb)
            srbtmp.append((srb[0],filtered_rigid_bodies))

        self.rigid_bodies=rbtmp
        self.floppy_bodies=fbtmp
        self.super_rigid_bodies=srbtmp

        ps["Rigid_Bodies_SimplifiedModel"]=(self.rigid_bodies,self.maxtrans_rb,self.maxrot_rb)
        ps["Floppy_Bodies_SimplifiedModel"]=(self.floppy_bodies,self.maxtrans_fb)
        ps["SR_Bodies_SimplifiedModel"]=(self.super_rigid_bodies,self.maxtrans_srb,self.maxrot_srb)
        return ps

    def set_output_level(self,level):
        self.output_level=level

    def get_output(self):
        output={}
        score=0.0

        output["SimplifiedModel_Total_Score_"+self.label]=str(self.m.evaluate(False))
        output["SimplifiedModel_Linker_Score_"+self.label]=str(self.linker_restraints.unprotected_evaluate(None))
        for name in self.sortedsegments_cr_dict:
            partialscore=self.sortedsegments_cr_dict[name].evaluate(False)
            score+=partialscore
            output["SimplifiedModel_Link_SortedSegments_"+name+"_"+self.label]=str(partialscore)
            partialscore=self.unmodeledregions_cr_dict[name].evaluate(False)
            score+=partialscore
            output["SimplifiedModel_Link_UnmodeledRegions_"+name+"_"+self.label]=str(partialscore)
        for name in self.linker_restraints_dict:
            output[name+"_"+self.label]=str(self.linker_restraints_dict[name].unprotected_evaluate(None))

        if len(self.reference_structures.keys())!=0:
           rmsds=self.get_all_rmsds()
           for label in rmsds:
               output["SimplifiedModel_"+label+"_"+self.label]=rmsds[label]

        if self.output_level=="high":
            for p in IMP.atom.get_leaves(self.prot):
                d=IMP.core.XYZR(p)
                output["Coordinates_"+p.get_name()+"_"+self.label]=str(d)


        output["_TotalScore"]=str(score)
        return output

    def get_test_output(self):
        # this method is called by test functions and return an enriched output
        output=self.get_output()
        for n,p in enumerate(self.get_particles_to_sample()):
            output["Particle_to_sample_"+str(n)]=str(p)
        output["Number_of_particles"]=len(IMP.atom.get_leaves(self.prot))
        output["Hierarchy_Dictionary"]=self.hier_dict.keys()
        output["Number_of_floppy_bodies"]=len(self.floppy_bodies)
        output["Number_of_rigid_bodies"]=len(self.rigid_bodies)
        output["Number_of_super_bodies"]=len(self.super_rigid_bodies)
        output["Selection_resolution_1"]=len(IMP.pmi.tools.select(self,resolution=1))
        output["Selection_resolution_5"]=len(IMP.pmi.tools.select(self,resolution=5))
        output["Selection_resolution_7"]=len(IMP.pmi.tools.select(self,resolution=5))
        output["Selection_resolution_10"]=len(IMP.pmi.tools.select(self,resolution=10))
        output["Selection_resolution_100"]=len(IMP.pmi.tools.select(self,resolution=100))
        output["Selection_All"]=len(IMP.pmi.tools.select(self))
        output["Selection_resolution=1"]=len(IMP.pmi.tools.select(self,resolution=1))
        output["Selection_resolution=1,resid=10"]=len(IMP.pmi.tools.select(self,resolution=1,residue=10))
        for resolution in self.hier_resolution:
           output["Hier_resolution_dictionary"+str(resolution)]=len(self.hier_resolution[resolution])
        for name in self.hier_dict:
           output["Selection_resolution=1,resid=10,name="+name]=len(IMP.pmi.tools.select(self,resolution=1,name=name,residue=10))
           output["Selection_resolution=1,resid=10,name="+name+",ambiguous"]=len(IMP.pmi.tools.select(self,resolution=1,name=name,name_is_ambiguous=True,residue=10))
           output["Selection_resolution=1,resid=10,name="+name+",ambiguous"]=len(IMP.pmi.tools.select(self,resolution=1,name=name,name_is_ambiguous=True,residue=10))
           output["Selection_resolution=1,resrange=(10,20),name="+name]=len(IMP.pmi.tools.select(self,resolution=1,name=name,first_residue=10,last_residue=20))
           output["Selection_resolution=1,resrange=(10,20),name="+name+",ambiguous"]=len(IMP.pmi.tools.select(self,resolution=1,name=name,name_is_ambiguous=True,first_residue=10,last_residue=20))
           output["Selection_resolution=10,resrange=(10,20),name="+name]=len(IMP.pmi.tools.select(self,resolution=10,name=name,first_residue=10,last_residue=20))
           output["Selection_resolution=10,resrange=(10,20),name="+name+",ambiguous"]=len(IMP.pmi.tools.select(self,resolution=10,name=name,name_is_ambiguous=True,first_residue=10,last_residue=20))
           output["Selection_resolution=100,resrange=(10,20),name="+name]=len(IMP.pmi.tools.select(self,resolution=100,name=name,first_residue=10,last_residue=20))
           output["Selection_resolution=100,resrange=(10,20),name="+name+",ambiguous"]=len(IMP.pmi.tools.select(self,resolution=100,name=name,name_is_ambiguous=True,first_residue=10,last_residue=20))

        return output


# Deprecation warning for the old SimplifiedModel class

class SimplifiedModel(Representation):
      def __init__(self,*args,**kwargs):
          Representation.__init__(self,*args,**kwargs)
          IMP.pmi.tools.print_deprecation_warning("SimplifiedModel","Representation")
