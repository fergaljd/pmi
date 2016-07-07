"""@namespace IMP.pmi.mmcif
   @brief Support for the mmCIF file format.
"""

from __future__ import print_function
import IMP.atom
import IMP.pmi.representation
import IMP.pmi.tools
from IMP.pmi.tools import OrderedDict
import IMP.pmi.output
import re
import sys
import os
import operator
import textwrap

class _LineWriter(object):
    def __init__(self, writer, line_len=80, multi_line_len=70):
        self.writer = writer
        self.line_len = line_len
        self.multi_line_len = multi_line_len
        self.column = 0
    def write(self, val):
        if isinstance(val, str) and len(val) > self.multi_line_len:
            self.writer.fh.write("\n;")
            for i in range(0, len(val), self.multi_line_len):
                self.writer.fh.write(val[i:i+self.multi_line_len])
                self.writer.fh.write("\n")
            self.writer.fh.write(";\n")
            self.column = 0
            return
        val = self.writer._repr(val)
        if self.column > 0:
            if self.column + len(val) + 1 > self.line_len:
                self.writer.fh.write("\n")
                self.column = 0
            else:
                self.writer.fh.write(" ")
                self.column += 1
        self.writer.fh.write(val)
        self.column += len(val)


class CifCategoryWriter(object):
    def __init__(self, writer, category):
        self.writer = writer
        self.category = category
    def write(self, **kwargs):
        self.writer._write(self.category, kwargs)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        pass


class CifLoopWriter(object):
    def __init__(self, writer, category, keys):
        self.writer = writer
        self.category = category
        self.keys = keys
    def write(self, **kwargs):
        l = _LineWriter(self.writer)
        for k in self.keys:
            l.write(kwargs.get(k, self.writer.omitted))
        self.writer.fh.write("\n")
    def __enter__(self):
        f = self.writer.fh
        f.write("#\nloop_\n")
        for k in self.keys:
            f.write("%s.%s\n" % (self.category, k))
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.writer.fh.write("#\n")


class CifWriter(object):
    omitted = '.'
    unknown = '?'

    def __init__(self, fh):
        self.fh = fh
    def category(self, category):
        return CifCategoryWriter(self, category)
    def loop(self, category, keys):
        return CifLoopWriter(self, category, keys)
    def write_comment(self, comment):
        for line in textwrap.wrap(comment, 78):
            self.fh.write('# ' + line + '\n')
    def _write(self, category, kwargs):
        for key in kwargs:
            self.fh.write("%s.%s %s\n" % (category, key,
                                          self._repr(kwargs[key])))
    def _repr(self, obj):
        if isinstance(obj, str) and '"' not in obj \
           and "'" not in obj and " " not in obj:
            return obj
        elif isinstance(obj, float):
            return "%.3f" % obj
        else:
            return repr(obj)


class Dumper(object):
    """Base class for helpers to dump output to mmCIF"""
    def __init__(self, simo):
        self.simo = simo

    def finalize(self):
        pass


class SoftwareDumper(Dumper):
    def dump(self, writer):
        with writer.loop("_software",
                         ["pdbx_ordinal", "name", "classification", "version",
                          "type", "location"]) as l:
            l.write(pdbx_ordinal=1, name="Integrative Modeling Platform (IMP)",
                    version=IMP.__version__, type="program",
                    classification="integrative model building",
                    location='https://integrativemodeling.org')
            l.write(pdbx_ordinal=2, name="IMP PMI module",
                    version=IMP.pmi.__version__, type="program",
                    classification="integrative model building",
                    location='https://integrativemodeling.org')


class EntityDumper(Dumper):
    def dump(self, writer):
        all_entities = [x for x in sorted(self.simo.entities.items(),
                                          key=operator.itemgetter(1))]
        with writer.loop("_entity",
                         ["id", "type", "src_method", "pdbx_description",
                          "formula_weight", "pdbx_number_of_molecules",
                          "details"]) as l:
            for name, entity_id in all_entities:
                l.write(id=entity_id, type='polymer', src_method='man',
                        pdbx_description=name, formula_weight=writer.unknown,
                        pdbx_number_of_molecules=1, details=writer.unknown)


class EntityPolyDumper(Dumper):
    def __init__(self, simo):
        super(EntityPolyDumper, self).__init__(simo)
        self.output = IMP.pmi.output.Output()

    def dump(self, writer):
        all_entities = [x for x in sorted(self.simo.entities.items(),
                                          key=operator.itemgetter(1))]
        with writer.loop("_entity_poly",
                         ["entity_id", "type", "nstd_linkage",
                          "nstd_monomer", "pdbx_strand_id",
                          "pdbx_seq_one_letter_code",
                          "pdbx_seq_one_letter_code_can"]) as l:
            for name, entity_id in all_entities:
                seq = self.simo.sequence_dict[name]
                chain = self.simo.chains[name]
                l.write(entity_id=entity_id, type='polypeptide(L)',
                        nstd_linkage='no', nstd_monomer='no',
                        pdbx_strand_id=self.output.chainids[chain],
                        pdbx_seq_one_letter_code=seq,
                        pdbx_seq_one_letter_code_can=seq)

class EntityPolySeqDumper(Dumper):
    def dump(self, writer):
        all_entities = [x for x in sorted(self.simo.entities.items(),
                                          key=operator.itemgetter(1))]
        with writer.loop("_entity_poly_seq",
                         ["entity_id", "num", "mon_id", "hetero"]) as l:
            for name, entity_id in all_entities:
                seq = self.simo.sequence_dict[name]
                for num, one_letter_code in enumerate(seq):
                    restyp = IMP.atom.get_residue_type(one_letter_code)
                    l.write(entity_id=entity_id, num=num + 1,
                            mon_id=restyp.get_string(),
                            hetero=CifWriter.omitted)

class StructAsymDumper(Dumper):
    def __init__(self, simo):
        super(StructAsymDumper, self).__init__(simo)
        self.output = IMP.pmi.output.Output()

    def dump(self, writer):
        all_entities = [x for x in sorted(self.simo.entities.items(),
                                          key=operator.itemgetter(1))]
        with writer.loop("_struct_asym",
                         ["id", "entity_id", "details"]) as l:
            for name, entity_id in all_entities:
                chain = self.simo.chains[name]
                l.write(id=self.output.chainids[chain],
                        entity_id=entity_id)

class _PDBFragment(object):
    """Record details about part of a PDB file used as input
       for a component."""
    primitive = 'sphere'
    granularity = 'by-residue'
    num = CifWriter.omitted
    def __init__(self, m, component, start, end, offset, pdbname, chain):
        self.component, self.start, self.end, self.offset, self.pdbname \
              = component, start, end, offset, pdbname
        sel = IMP.atom.NonWaterNonHydrogenPDBSelector() \
              & IMP.atom.ChainPDBSelector(chain)
        self.hier = IMP.atom.read_pdb(pdbname, m, sel)

    def combine(self, other):
        pass

class _BeadsFragment(object):
    """Record details about beads used to represent part of a component."""
    primitive = 'sphere'
    granularity = 'by-feature'
    def __init__(self, m, component, start, end, num):
        self.component, self.start, self.end, self.num \
              = component, start, end, num

    def combine(self, other):
        if type(other) == type(self) and other.start == self.end + 1:
            self.end = other.end
            self.num += other.num
            return True

class _StartingModel(object):
    """Record details about an input model (e.g. comparative modeling
       template) used for a component."""

    source = CifWriter.unknown
    db_name = CifWriter.unknown
    db_code = CifWriter.unknown
    sequence_identity = CifWriter.unknown

    def __init__(self, fragment):
        self.fragments = [fragment]

class ModelRepresentationDumper(Dumper):
    def __init__(self, simo):
        super(ModelRepresentationDumper, self).__init__(simo)
        # dict of fragments, ordered by component name
        self.fragments = OrderedDict()

    def add_fragment(self, fragment):
        """Add a model fragment."""
        comp = fragment.component
        if comp not in self.fragments:
            self.fragments[comp] = []
        fragments = self.fragments[comp]
        if len(fragments) == 0 or not fragments[-1].combine(fragment):
            fragments.append(fragment)

    def dump(self, writer):
        segment_id = 1
        with writer.loop("_ihm_model_representation",
                         ["segment_id", "entity_id", "entity_description",
                          "seq_id_begin", "seq_id_end",
                          "model_object_primitive", "starting_model_id",
                          "model_mode", "model_granularity",
                          "model_object_count"]) as l:
            for comp, fragments in self.fragments.items():
                for f in fragments:
                    starting_model_id = CifWriter.omitted
                    if hasattr(f, 'pdbname'):
                        starting_model_id = self.starting_model_id[f.pdbname]
                    l.write(segment_id=segment_id,
                            entity_id=self.simo.entities[f.component],
                            entity_description=f.component,
                            seq_id_begin=f.start,
                            seq_id_end=f.end,
                            model_object_primitive=f.primitive,
                            starting_model_id=starting_model_id,
                            model_granularity=f.granularity,
                            model_object_count=f.num)
                    segment_id += 1

class PDBSource(object):
    """An experimental PDB file used as part of a starting model"""
    source = 'experimental model'
    db_name = 'PDB'
    chain_id = CifWriter.unknown
    sequence_identity = 100.0

    def __init__(self, model, db_code):
        self.db_code = db_code
        # Assume the structure covers the entire sequence
        self.seq_id_begin = model.seq_id_begin
        self.seq_id_end = model.seq_id_end

class TemplateSource(object):
    """A PDB file used as a template for a comparative starting model"""
    source = 'comparative model'
    db_name = 'PDB'

    def __init__(self, code, seq_id_begin, seq_id_end, seq_id,
                 model):
        # Assume a code of 1abcX refers to a real PDB structure
        if len(code) == 5:
            self.db_code = code[:4].upper()
            self.chain_id = code[4]
        else:
            self.db_code = self.chain_id = CifWriter.unknown
        self.sequence_identity = seq_id
        # The template may cover more than the current starting model
        self.seq_id_begin = max(model.seq_id_begin, seq_id_begin)
        self.seq_id_end = min(model.seq_id_end, seq_id_end)

class UnknownSource(object):
    """Part of a starting model from an unknown source"""
    source = CifWriter.unknown
    db_code = CifWriter.unknown
    db_name = CifWriter.unknown
    chain_id = CifWriter.unknown
    sequence_identity = CifWriter.unknown

    def __init__(self, model):
        self.seq_id_begin = model.seq_id_begin
        self.seq_id_end = model.seq_id_end

class DatasetLocation(object):
    """External location of a dataset"""
    pass

class RepoDatasetLocation(DatasetLocation):
    """Pointer to a dataset stored in a repository"""
    doi = content_filename = CifWriter.unknown

    def __init__(self, repo, fname):
        if repo:
            self.doi = repo.doi
            self.content_filename = repo.get_fname(fname)

class DBDatasetLocation(DatasetLocation):
    """Pointer to a dataset stored in an official database (e.g. PDB)"""
    version = CifWriter.omitted
    details = CifWriter.omitted

    def __init__(self, db_name, db_code):
        self.db_name = db_name
        self.access_code = db_code

class Dataset(object):
    group_id = 1
    location = None

    def set_location(self, repo, fname):
        self.location = RepoDatasetLocation(repo, fname)

class CXMSDataset(Dataset):
    data_type = 'CX-MS data'

class CompModelDataset(Dataset):
    """A comparative model dataset.
       Currently it is assumed that models are stored in a repository."""
    data_type = 'Comparative model'
    def __init__(self, repo, fname):
        self.set_location(repo, fname)

class PDBDataset(Dataset):
    """An experimental PDB structure dataset."""
    data_type = 'unspecified' # todo: missing enumeration?
    def __init__(self, db_code):
        self.location = DBDatasetLocation('PDB', db_code)


class DatasetDumper(Dumper):
    def __init__(self, simo):
        super(DatasetDumper, self).__init__(simo)
        self.datasets = []

    def add(self, dataset):
        self.datasets.append(dataset)
        dataset.id = len(self.datasets)

    def dump(self, writer):
        with writer.loop("_ihm_dataset_list",
                         ["id", "group_id", "data_type",
                          "database_hosted"]) as l:
            for d in self.datasets:
                l.write(id=d.id, group_id=d.group_id, data_type=d.data_type,
                        database_hosted=not isinstance(d.location,
                                                       RepoDatasetLocation))
        others = [d for d in self.datasets
                  if isinstance(d.location, RepoDatasetLocation)]
        if len(others) > 0:
            self.dump_other(others, writer)
        rel_dbs = [d for d in self.datasets
                   if isinstance(d.location, DBDatasetLocation)]
        if len(rel_dbs) > 0:
            self.dump_rel_dbs(rel_dbs, writer)

    def dump_rel_dbs(self, datasets, writer):
        ordinal = 1
        with writer.loop("_ihm_dataset_related_db_reference",
                         ["id", "dataset_list_id", "db_name",
                          "access_code", "version", "data_type",
                          "details"]) as l:
            for d in datasets:
                l.write(id=ordinal, dataset_list_id=d.id,
                        db_name=d.location.db_name,
                        access_code=d.location.access_code,
                        version=d.location.version,
                        data_type=d.data_type, details=d.location.details)
                ordinal += 1

    def dump_other(self, datasets, writer):
        ordinal = 1
        with writer.loop("_ihm_dataset_other",
                         ["id", "dataset_list_id", "data_type",
                          "doi", "content_filename"]) as l:
            for d in datasets:
                l.write(id=ordinal, dataset_list_id=d.id,
                        data_type=d.data_type, doi=d.location.doi,
                        content_filename=d.location.content_filename)
                ordinal += 1


class ExperimentalCrossLink(object):
    def __init__(self, r1, c1, r2, c2, label, dataset):
        self.r1, self.c1, self.r2, self.c2, self.label = r1, c1, r2, c2, label
        self.dataset = dataset

class CrossLink(object):
    def __init__(self, ex_xl, p1, p2, sigma1, sigma2, psi):
        self.ex_xl, self.sigma1, self.sigma2 = ex_xl, sigma1, sigma2
        self.p1, self.p2 = p1, p2
        self.psi = psi

class CrossLinkDumper(Dumper):
    def __init__(self, simo):
        super(CrossLinkDumper, self).__init__(simo)
        self.cross_links = []
        self.exp_cross_links = []

    def add_experimental(self, cross_link):
        self.exp_cross_links.append(cross_link)
        cross_link.id = len(self.exp_cross_links)

    def add(self, cross_link):
        self.cross_links.append(cross_link)
        cross_link.id = len(self.cross_links)

    def dump(self, writer):
        self.dump_list(writer)
        self.dump_restraint(writer)

    def dump_list(self, writer):
        with writer.loop("_ihm_cross_link_list",
                         ["id", "group_id", "entity_description_1",
                          "entity_id_1", "seq_id_1", "comp_id_1",
                          "entity_description_2",
                          "entity_id_2", "seq_id_2", "comp_id_2", "type",
                          "dataset_list_id"]) as l:
            for xl in self.exp_cross_links:
                seq1 = self.simo.sequence_dict[xl.c1]
                seq2 = self.simo.sequence_dict[xl.c2]
                rt1 = IMP.atom.get_residue_type(seq1[xl.r1-1])
                rt2 = IMP.atom.get_residue_type(seq2[xl.r2-1])
                l.write(id=xl.id,
                        entity_description_1=xl.c1,
                        entity_id_1=self.simo.entities[xl.c1],
                        seq_id_1=xl.r1,
                        comp_id_1=rt1.get_string(),
                        entity_description_2=xl.c2,
                        entity_id_2=self.simo.entities[xl.c2],
                        seq_id_2=xl.r2,
                        comp_id_2=rt2.get_string(),
                        type=xl.label,
                        dataset_list_id=xl.dataset.id)

    def dump_restraint(self, writer):
        with writer.loop("_ihm_cross_link_restraint",
                         ["id", "group_id", "entity_id_1", "asym_id_1",
                          "seq_id_1", "comp_id_1",
                          "entity_id_2", "asym_id_2", "seq_id_2", "comp_id_2",
                          "type", "psi", "sigma_1", "sigma_2"]) as l:
            for xl in self.cross_links:
                seq1 = self.simo.sequence_dict[xl.ex_xl.c1]
                seq2 = self.simo.sequence_dict[xl.ex_xl.c2]
                rt1 = IMP.atom.get_residue_type(seq1[xl.ex_xl.r1-1])
                rt2 = IMP.atom.get_residue_type(seq2[xl.ex_xl.r2-1])
                # todo: get chain ids for xl.p1 and xl.p2
                l.write(id=xl.id,
                        group_id=xl.ex_xl.id,
                        entity_id_1=self.simo.entities[xl.ex_xl.c1],
                        seq_id_1=xl.ex_xl.r1,
                        comp_id_1=rt1.get_string(),
                        entity_id_2=self.simo.entities[xl.ex_xl.c2],
                        seq_id_2=xl.ex_xl.r2,
                        comp_id_2=rt2.get_string(),
                        type=xl.ex_xl.label,
                        psi=xl.psi, sigma_1=xl.sigma1, sigma_2=xl.sigma2)


class StartingModelDumper(Dumper):
    def __init__(self, simo):
        super(StartingModelDumper, self).__init__(simo)
        # dict of PDB fragments, ordered by component name
        self.fragments = OrderedDict()
        # dict of starting models (entire PDB files), collected from fragments
        self.models = OrderedDict()
        # mapping from pdbname to starting_model_id
        self.starting_model_id = {}

    def add_pdb_fragment(self, fragment):
        """Add a starting model PDB fragment."""
        comp = fragment.component
        if comp not in self.fragments:
            self.fragments[comp] = []
            self.models[comp] = []
        self.fragments[comp].append(fragment)
        models = self.models[comp]
        if len(models) == 0 \
           or models[-1].fragments[0].pdbname != fragment.pdbname:
            models.append(_StartingModel(fragment))
        else:
            models[-1].fragments.append(fragment)

    def get_templates(self, pdbname, model):
        templates = []
        tmpre = re.compile('REMARK   6 TEMPLATE: (\S+) .* '
                           'MODELS (\S+):\S+ \- (\S+):\S+ AT (\S+)%')

        with open(pdbname) as fh:
            for line in fh:
                if line.startswith('ATOM'): # Read only the header
                    break
                m = tmpre.match(line)
                if m:
                    templates.append(TemplateSource(m.group(1),
                                                    int(m.group(2)),
                                                    int(m.group(3)),
                                                    m.group(4), model))
        # Sort by starting residue, then ending residue
        return sorted(templates, key=lambda x: (x.seq_id_begin, x.seq_id_end))

    def get_sources(self, model, pdbname):
        # Attempt to identity PDB file vs. comparative model
        first_line = open(pdbname).readline()
        if first_line.startswith('HEADER'):
            source = PDBSource(model, first_line[62:66].strip())
            model.dataset = PDBDataset(source.db_code)
            self.simo.dataset_dump.add(model.dataset)
            return [source]
        elif first_line.startswith('EXPDTA    THEORETICAL MODEL, MODELLER'):
            model.dataset = CompModelDataset(self.simo._repo, pdbname)
            self.simo.dataset_dump.add(model.dataset)
            templates = self.get_templates(pdbname, model)
            if templates:
                return templates
        return [UnknownSource(model)]

    def assign_model_details(self):
        for comp, models in self.models.items():
            for i, model in enumerate(models):
                model.name = "%s-m%d" % (comp, i+1)
                self.starting_model_id[model.fragments[0].pdbname] = model.name
                model.seq_id_begin = min(x.start + x.offset
                                         for x in model.fragments)
                model.seq_id_end = max(x.end + x.offset
                                       for x in model.fragments)
                model.sources = self.get_sources(model,
                                                 model.fragments[0].pdbname)

    def all_models(self):
        for comp, models in self.models.items():
            for model in models:
                yield model

    def finalize(self):
        self.assign_model_details()

    def dump(self, writer):
        self.dump_details(writer)
        self.dump_coords(writer)

    def dump_details(self, writer):
        writer.write_comment("""IMP will attempt to identify which input models
are crystal structures and which are comparative models, but does not have
sufficient information to deduce all of the templates used for comparative
modeling. These may need to be added manually below.""")
        with writer.loop("_ihm_starting_model_details",
                     ["id", "entity_id", "entity_description", "seq_id_begin",
                      "seq_id_end", "starting_model_source",
                      "starting_model_db_name", "starting_model_db_code",
                      "starting_model_db_pdb_auth_seq_id",
                      "starting_model_sequence_identity",
                      "starting_model_id",
                      "dataset_list_id"]) as l:
            ordinal = 1
            for model in self.all_models():
                f = model.fragments[0]
                for source in model.sources:
                    l.write(id=ordinal,
                      entity_id=self.simo.entities[f.component],
                      entity_description=f.component,
                      seq_id_begin=source.seq_id_begin,
                      seq_id_end=source.seq_id_end,
                      starting_model_db_pdb_auth_seq_id=source.chain_id,
                      starting_model_id=model.name,
                      starting_model_source=source.source,
                      starting_model_db_name=source.db_name,
                      starting_model_db_code=source.db_code,
                      starting_model_sequence_identity=source.sequence_identity,
                      dataset_list_id=model.dataset.id)
                    ordinal += 1

    def dump_coords(self, writer):
        ordinal = 1
        with writer.loop("_ihm_starting_model_coord",
                     ["starting_model_id", "group_PDB", "id", "type_symbol",
                      "atom_id", "comp_id", "entity_id", "seq_id", "Cartn_x",
                      "Cartn_y", "Cartn_z", "B_iso_or_equiv",
                      "ordinal_id"]) as l:
            for model in self.all_models():
                for f in model.fragments:
                    for a in IMP.atom.get_leaves(f.hier):
                        coord = IMP.core.XYZ(a).get_coordinates()
                        atom = IMP.atom.Atom(a)
                        element = atom.get_element()
                        element = IMP.atom.get_element_table().get_name(element)
                        atom_name = atom.get_atom_type().get_string()
                        group_pdb = 'ATOM'
                        if atom_name.startswith('HET:'):
                            group_pdb = 'HETATM'
                            del atom_name[:4]
                        res = IMP.atom.get_residue(atom)
                        res_name = res.get_residue_type().get_string()
                        chain = IMP.atom.get_chain(res)
                        l.write(starting_model_id=model.name,
                                group_PDB=group_pdb,
                                id=atom.get_input_index(), type_symbol=element,
                                atom_id=atom_name, comp_id=res_name,
                                entity_id=self.simo.entities[f.component],
                                seq_id=res.get_index(), Cartn_x=coord[0],
                                Cartn_y=coord[1], Cartn_z=coord[2],
                                B_iso_or_equiv=atom.get_temperature_factor(),
                                ordinal_id=ordinal)
                        ordinal += 1


class CifEntities(dict):
    """Handle mapping from IMP components to CIF entity IDs.
       An entity is a chain with a unique sequence. Thus, multiple
       components may map to the same entity if they share sequence."""
    def __init__(self):
        super(CifEntities, self).__init__()
        self._sequence_dict = {}

    def add(self, component_name, sequence):
        if sequence not in self._sequence_dict:
            entity_id = len(self._sequence_dict) + 1
            self._sequence_dict[sequence] = entity_id
            self[component_name] = entity_id


class Representation(IMP.pmi.representation.Representation):
    def __init__(self, m, fh, *args, **kwargs):
        self._cif_writer = CifWriter(fh)
        self.entities = CifEntities()
        self.chains = {}
        self.model_repr_dump = ModelRepresentationDumper(self)
        self.cross_link_dump = CrossLinkDumper(self)
        self.dataset_dump = DatasetDumper(self)
        self.starting_model_dump = StartingModelDumper(self)
        self.model_repr_dump.starting_model_id \
                    = self.starting_model_dump.starting_model_id
        self._dumpers = [SoftwareDumper(self), EntityDumper(self),
                         EntityPolyDumper(self), EntityPolySeqDumper(self),
                         StructAsymDumper(self),
                         self.model_repr_dump, self.dataset_dump,
                         self.cross_link_dump,
                         self.starting_model_dump]
        super(Representation, self).__init__(m, *args, **kwargs)

    def create_component(self, name, *args, **kwargs):
        super(Representation, self).create_component(name, *args, **kwargs)
        self.chains[name] = len(self.chains)

    def add_component_sequence(self, name, *args, **kwargs):
        super(Representation, self).add_component_sequence(name, *args,
                                                           **kwargs)
        self.entities.add(name, self.sequence_dict[name])

    def flush(self):
        for dumper in self._dumpers:
            dumper.finalize()
        for dumper in self._dumpers:
            dumper.dump(self._cif_writer)

    def _add_pdb_element(self, name, start, end, offset, pdbname, chain):
        p = _PDBFragment(self.m, name, start, end, offset, pdbname, chain)
        self.model_repr_dump.add_fragment(p)
        self.starting_model_dump.add_pdb_fragment(p)

    def _add_bead_element(self, name, start, end, num):
        b = _BeadsFragment(self.m, name, start, end, num)
        self.model_repr_dump.add_fragment(b)

    def _get_cross_link_dataset(self, fname):
        d = CXMSDataset()
        d.set_location(self._repo, fname)
        self.dataset_dump.add(d)
        return d

    def _add_experimental_cross_link(self, r1, c1, r2, c2, label, dataset):
        xl = ExperimentalCrossLink(r1, c1, r2, c2, label, dataset)
        self.cross_link_dump.add_experimental(xl)
        return xl

    def _add_cross_link(self, ex_xl, p1, p2, sigma1, sigma2, psi):
        self.cross_link_dump.add(CrossLink(ex_xl, p1, p2, sigma1, sigma2, psi))
