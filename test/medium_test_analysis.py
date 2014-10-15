import IMP.pmi
import IMP.pmi.analysis
import IMP.pmi.io.input
import IMP.test
import RMF
import IMP.rmf
import os,sys
from math import sqrt


class AnalysisTest(IMP.test.TestCase):
    def setUp(self):
        IMP.test.TestCase.setUp(self)
        self.model = IMP.Model()

    def test_alignment_simple(self):
        """Test alignment, random transformation"""
        m=IMP.Model()
        xyz10=IMP.algebra.Vector3D(1,0,0)
        xyz20=IMP.algebra.Vector3D(0,0,0)
        xyz11=IMP.algebra.Vector3D(1,0,0)
        xyz21=IMP.algebra.Vector3D(0,0,0)

        # get random transformation
        ub = IMP.algebra.Vector3D(-10, -10, -10)
        lb = IMP.algebra.Vector3D(10, 10, 10)
        bb = IMP.algebra.BoundingBox3D(ub, lb)
        translation = IMP.algebra.get_random_vector_in(bb)
        rotation = IMP.algebra.get_random_rotation_3d()
        transformation = IMP.algebra.Transformation3D(
                   rotation,translation)

        # decorate particles
        d10=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz10)
        d20=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz20)
        d11=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz11)
        d21=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz21)

        # apply transformation to second coordinate set
        IMP.core.transform(d11,transformation)
        IMP.core.transform(d21,transformation)

        # get the new coordinates
        xyz11=d11.get_coordinates()
        xyz21=d21.get_coordinates()

        # define the coordinate dictionary
        coord_dict_0={"prot1":[xyz10],"prot2":[xyz20]}
        coord_dict_1={"prot1":[xyz11],"prot2":[xyz21]}

        # initialize the alignment class
        ali=IMP.pmi.analysis.Alignment(coord_dict_0,coord_dict_1)
        (rmsd,transformation)=ali.align()

        # test output
        self.assertAlmostEqual(rmsd,0.0)
        IMP.core.transform(d11,transformation)
        IMP.core.transform(d21,transformation)

        xyz11=d11.get_coordinates()
        xyz21=d21.get_coordinates()
        for i in [0,1,2]:
            self.assertAlmostEqual(xyz11[i],xyz10[i])
            self.assertAlmostEqual(xyz21[i],xyz20[i])




    def test_alignment_and_rmsd(self):
        """Test alignment, random transformation"""
        m=IMP.Model()
        xyz10=IMP.algebra.Vector3D(1,0,0)
        xyz20=IMP.algebra.Vector3D(0,0,1)
        xyz30=IMP.algebra.Vector3D(0,1,0)
        xyz40=IMP.algebra.Vector3D(1,1,1)
        xyz11=IMP.algebra.Vector3D(1,0,0)
        xyz21=IMP.algebra.Vector3D(0,0,1)
        xyz31=IMP.algebra.Vector3D(0,1,0)
        xyz41=IMP.algebra.Vector3D(2,1,1)

        # get random transformation
        ub = IMP.algebra.Vector3D(-10, -10, -10)
        lb = IMP.algebra.Vector3D(10, 10, 10)
        bb = IMP.algebra.BoundingBox3D(ub, lb)
        translation = IMP.algebra.get_random_vector_in(bb)
        rotation = IMP.algebra.get_random_rotation_3d()
        transformation = IMP.algebra.Transformation3D(
                   rotation,translation)

        # decorate particles
        d10=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz10)
        d20=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz20)
        d30=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz30)
        d40=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz40)
        d11=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz11)
        d21=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz21)
        d31=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz31)
        d41=IMP.core.XYZ.setup_particle(IMP.Particle(m),xyz41)

        # apply transformation to second coordinate set
        IMP.core.transform(d11,transformation)
        IMP.core.transform(d21,transformation)
        IMP.core.transform(d31,transformation)
        IMP.core.transform(d41,transformation)

        # get the new coordinates
        xyz11=d11.get_coordinates()
        xyz21=d21.get_coordinates()
        xyz31=d31.get_coordinates()
        xyz41=d31.get_coordinates()
        # define the coordinate dictionary
        coord_ali_dict_0={"prot1":[xyz10],"prot2":[xyz20],"prot3":[xyz30]}
        coord_ali_dict_1={"prot1":[xyz11],"prot2":[xyz21],"prot3":[xyz31]}


        # initialize the alignment class
        ali=IMP.pmi.analysis.Alignment(coord_ali_dict_0,coord_ali_dict_1)
        (rmsd,transformation)=ali.align()

        # test output
        self.assertAlmostEqual(rmsd,0.0)
        IMP.core.transform(d11,transformation)
        IMP.core.transform(d21,transformation)
        IMP.core.transform(d31,transformation)
        IMP.core.transform(d41,transformation)

        xyz11=d11.get_coordinates()
        xyz21=d21.get_coordinates()
        xyz31=d31.get_coordinates()
        xyz41=d41.get_coordinates()

        coord_rmsd_dict_0={"prot1":[xyz10],"prot2":[xyz20],"prot3":[xyz30],"prot4":[xyz40]}
        coord_rmsd_dict_1={"prot1":[xyz11],"prot2":[xyz21],"prot3":[xyz31],"prot4":[xyz41]}
        ali=IMP.pmi.analysis.Alignment(coord_rmsd_dict_0,coord_rmsd_dict_1)
        self.assertAlmostEqual(ali.get_rmsd(),1.0/sqrt(4.0))

    def test_alignment_rmsd(self):
        """Test rmsd of already aligned particles,
        handles multiple copies of same protein"""

        xyz10=IMP.algebra.Vector3D(0,0,0)
        xyz20=IMP.algebra.Vector3D(1,1,1)
        xyz11=IMP.algebra.Vector3D(0,0,0)
        xyz21=IMP.algebra.Vector3D(2,1,1)

        coord_dict_0={"prot1":[xyz10],"prot2":[xyz20]}
        coord_dict_1={"prot1":[xyz11],"prot2":[xyz21]}

        ali=IMP.pmi.analysis.Alignment(coord_dict_0,coord_dict_1)
        self.assertAlmostEqual(ali.get_rmsd(),1.0/sqrt(2.0))

    def test_alignment_rmsd_with_permutation(self):
        """Test rmsd of already aligned particles,
        handles multiple copies of same protein"""

        xyz10=IMP.algebra.Vector3D(0,0,0)
        xyz20=IMP.algebra.Vector3D(1,1,1)
        xyz30=IMP.algebra.Vector3D(2,2,2)
        xyz11=IMP.algebra.Vector3D(0,0,0)
        xyz21=IMP.algebra.Vector3D(2,2,2)
        xyz31=IMP.algebra.Vector3D(2,1,1)

        coord_dict_0={"prot1":[xyz10],"prot2..1":[xyz20],"prot2..2":[xyz30]}
        coord_dict_1={"prot1":[xyz11],"prot2..1":[xyz21],"prot2..2":[xyz31]}

        ali=IMP.pmi.analysis.Alignment(coord_dict_0,coord_dict_1)
        self.assertAlmostEqual(ali.get_rmsd(),1.0/sqrt(3.0))


    def test_alignment_rmsd_with_weights(self):
        """Test rmsd of already aligned particles,
        handles multiple copies of same protein"""

        xyz10=IMP.algebra.Vector3D(0,0,0)
        xyz20=IMP.algebra.Vector3D(1,1,1)
        xyz11=IMP.algebra.Vector3D(0,0,0)
        xyz21=IMP.algebra.Vector3D(2,1,1)

        coord_dict_0={"prot1":[xyz10],"prot2":[xyz20]}
        coord_dict_1={"prot1":[xyz11],"prot2":[xyz21]}

        weights={"prot1":[1.0],"prot2":[10.0]}
        ali=IMP.pmi.analysis.Alignment(coord_dict_0,coord_dict_1,weights)
        self.assertAlmostEqual(ali.get_rmsd(),sqrt(10.0/11.0))

    def precision(self):
        pass

    def test_get_model_density(self):
        """Test GetModelDensity correctly creates and adds density maps"""
        custom_ranges={'med2':[(1,100,'med2')],
                       'med16':['med16']}
        mdens = IMP.pmi.analysis.GetModelDensity(custom_ranges)
        rmf_file=self.get_input_file_name('output/rmfs/2.rmf3')
        rh = RMF.open_rmf_file_read_only(rmf_file)
        prots = IMP.rmf.create_hierarchies(rh,self.model)
        IMP.rmf.load_frame(rh,0)
        mdens.add_subunits_density(prots[0])
        self.assertEqual(mdens.get_density_keys(),['med2','med16'])
        med2_coords=[]
        med16_coords=[]
        for i in range(4):
            IMP.rmf.load_frame(rh,i)
            s2=[child for child in prots[0].get_children()
                      if child.get_name() == 'med2']
            med2_coords+=[IMP.core.XYZ(p).get_coordinates() for p in
                         IMP.atom.Selection(s2,residue_indexes=range(1,100+1)).get_selected_particles()]
            s16=[child for child in prots[0].get_children()
                      if child.get_name() == 'med16']
            med16_coords+=[IMP.core.XYZ(p).get_coordinates() for p in
                           IMP.atom.Selection(s16).get_selected_particles()]
            mdens.add_subunits_density(prots[0])

        bbox2=IMP.algebra.BoundingBox3D(med2_coords)
        bbox16=IMP.algebra.BoundingBox3D(med16_coords)
        self.assertTrue(IMP.em.get_bounding_box(mdens.get_density('med2')).get_contains(bbox2))
        self.assertTrue(IMP.em.get_bounding_box(mdens.get_density('med16')).get_contains(bbox16))

    def test_analysis_macro(self):
        """Test the analysis macro does everything correctly"""
        pass

class ClusteringTest(IMP.test.TestCase):
    def setUp(self):
        IMP.test.TestCase.setUp(self)
        self.model = IMP.Model()

    def test_dist_matrix(self):
        """Test clustering can calculate distance matrix, align, and cluster correctly"""
        xyz10=IMP.algebra.Vector3D(0,0,0)
        xyz20=IMP.algebra.Vector3D(1,1,1)
        xyz30=IMP.algebra.Vector3D(2,2,2)

        xyz11=IMP.algebra.Vector3D(0,0,0)
        xyz21=IMP.algebra.Vector3D(2,2,2)
        xyz31=IMP.algebra.Vector3D(2,1,1)

        xyz12=IMP.algebra.Vector3D(0,0,0)
        xyz22=IMP.algebra.Vector3D(2,2,2)
        xyz32=IMP.algebra.Vector3D(1,1,1)

        coord_dict_0={"prot1":[xyz10],"prot2..1":[xyz20],"prot2..2":[xyz30]}
        coord_dict_1={"prot1":[xyz11],"prot2..1":[xyz21],"prot2..2":[xyz31]}
        coord_dict_2={"prot1":[xyz12],"prot2..1":[xyz22],"prot2..2":[xyz32]}

        weights={"prot1":[1.0],"prot2..1":[10.0],"prot2..2":[10.0]}

        clu=IMP.pmi.analysis.Clustering(weights)

        clu.fill(0,coord_dict_0)
        clu.fill(1,coord_dict_1)
        clu.fill(2,coord_dict_2)

        clu.dist_matrix()
        d=clu.get_dist_matrix()
        self.assertAlmostEqual(d[0,0],0.0)
        self.assertAlmostEqual(d[1,0],sqrt(10.0/21.0))
        self.assertAlmostEqual(d[2,0],0.0)

if __name__ == '__main__':
    IMP.test.main()
