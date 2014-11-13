import IMP
import IMP.pmi
import IMP.pmi.topology
import IMP.pmi.macros
import os
import IMP.test
import IMP.rmf
import RMF

def children_as_dict(h):
    cdict={}
    for c in h.get_children():
        cdict[c.get_name()]=c
    return cdict

class TopologyReaderTests(IMP.test.TestCase):

    def test_reading(self):
        '''Test basic reading'''
        topology_file=self.get_input_file_name("topology.txt")
        t=IMP.pmi.topology.TopologyReader(topology_file)
        self.assertEqual(len(t.component_list),3)
        self.assertEqual(t.component_list[0].domain_name,"Rpb1_1")
        self.assertEqual(t.component_list[1].name,"Rpb1")
        self.assertEqual(t.component_list[2].domain_name,"Rpb4")
        self.assertEqual(t.component_list[2].name,"Rpb4")

    def test_round_trip(self):
        '''Test reading and writing'''
        topology_file=self.get_input_file_name("topology.txt")
        outfile = self.get_tmp_file_name("ttest.txt")
        t=IMP.pmi.topology.TopologyReader(topology_file)
        t.write_topology_file(outfile)

        t=IMP.pmi.topology.TopologyReader(outfile)
        self.assertEqual(len(t.component_list),3)
        self.assertEqual(t.component_list[0].domain_name,"Rpb1_1")
        self.assertEqual(t.component_list[1].name,"Rpb1")
        self.assertEqual(t.component_list[2].domain_name,"Rpb4")
        self.assertEqual(t.component_list[2].name,"Rpb4")

    def test_build(self):
        '''Test building with macro BuildModel1 using a topology file'''
        topology_file=self.get_input_file_name("topology.txt")

        m = IMP.Model()
        simo = IMP.pmi.representation.Representation(m,upperharmonic=True,disorderedlength=False)
        bm=IMP.pmi.macros.BuildModel1(simo)

        t=IMP.pmi.topology.TopologyReader(topology_file)
        self.assertEqual(t.defaults['gmm_dir'],'./')
        bm.build_model(component_topologies=t.component_list,
                       force_create_gmm_files=True)
        o = IMP.pmi.output.Output()
        rmf_fn = self.get_tmp_file_name("buildmodeltest.rmf")
        o.init_rmf(rmf_fn, [simo.prot])
        o.write_rmf(rmf_fn)
        o.close_rmf(rmf_fn)
        f = RMF.open_rmf_file_read_only(rmf_fn)
        r = IMP.rmf.create_hierarchies(f, m)[0]
        IMP.rmf.load_frame(f, 0)
        self.assertEqual(len(r.get_children()),2)
        cdict=children_as_dict(r)
        self.assertEqual(set([c.get_name() for c in cdict["Rpb1"].get_children()]),
                         set(["Beads" , "Rpb1_Res:1" , "Rpb1_Res:10"]))
        self.assertEqual(set([c.get_name() for c in cdict["Rpb4"].get_children()]),
                         set(["Beads", "Rpb4_Res:0","Rpb4_Res:1", "Rpb4_Res:10","Densities"]))
        r1dict=children_as_dict(cdict["Rpb1"])
        self.assertEqual(len(r1dict["Rpb1_Res:1"].get_children()),6)
        r4dict=children_as_dict(cdict["Rpb4"])
        self.assertEqual(len(r4dict["Densities"].get_children()[0].get_children()),3)

    def test_build_with_movers(self):
        '''Check if rigid bodies etc are set up as requested'''
        pass
if __name__=="__main__":
    IMP.test.main()
