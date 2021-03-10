import ROOT
ROOT.gROOT.SetBatch(True)
ROOT.EnableImplicitMT()


def selections(df):
    # Apply the baseline selection and the selection on the muon and tau collections
    df = df.Filter("HLT_IsoMu17_eta2p1_LooseIsoPFTau20 == true && nMuon > 0 && nTau > 0")\
           .Define("goodMuons", "abs(Muon_eta) < 2.1 && Muon_pt > 17 && Muon_tightId == true")\
           .Filter("Sum(goodMuons) > 0")\
           .Define("goodTaus", "Tau_charge != 0 && abs(Tau_eta) < 2.3 && Tau_pt > 20 && Tau_idDecayMode == true && Tau_idIsoTight == true && Tau_idAntiEleTight == true && Tau_idAntiMuTight == true")\
           .Filter("Sum(goodTaus) > 0")

    # Add new columns for the good muons and taus
    for lepton in ['Muon', 'Tau']:
        cols = ['pt', 'eta', 'phi', 'mass', 'charge']
        if lepton == 'Tau':
            cols.append('relIso_all')
        for col in cols:
            df = df.Define('good{}_{}'.format(lepton, col), '{}_{}[good{}s]'.format(lepton, col, lepton))

    return df


# Jit a function to find the muon-tau pair
ROOT.gInterpreter.Declare('''
using VecF_t = const ROOT::RVec<float>&;
using VecI_t = const ROOT::RVec<int>&;
vector<int>
findMuonTauPair(
    VecF_t Muon_pt, VecF_t Muon_eta, VecF_t Muon_phi, VecI_t Muon_charge,
    VecF_t Tau_relIso_all, VecF_t Tau_eta, VecF_t Tau_phi, VecI_t Tau_charge)
{
    using namespace ROOT::VecOps;
    auto Muon_idx = Reverse(Argsort(Muon_pt)); // max to min
    auto Tau_idx = Argsort(Tau_relIso_all); // min to max
    for (int Muon_i : Muon_idx) {
        for (int Tau_i: Tau_idx) {
            if (DeltaR(Muon_eta[Muon_i], Tau_eta[Tau_i], Muon_phi[Muon_i], Tau_phi[Tau_i]) > 0.5 && Muon_charge[Muon_i] * Tau_charge[Tau_i] < 0) {
                return {Muon_i, Tau_i};
            }
        }
    }

    return {}; // Invalid event!
}
''')


# Find the muon tau pair with the function jitted above
def find_pair(df):
    return df.Define('idxs', 'findMuonTauPair(goodMuon_pt, goodMuon_eta, goodMuon_phi, goodMuon_charge, goodTau_relIso_all, goodTau_eta, goodTau_phi, goodTau_charge)')\
             .Filter('idxs.size() == 2');


# Jit a function to compute the invariant mass
ROOT.gInterpreter.Declare('''
float computeInvariantMass(float pt_1, float eta_1, float phi_1, float mass_1, float pt_2, float eta_2, float phi_2, float mass_2) {
    auto p1 = ROOT::Math::PtEtaPhiMVector(pt_1, eta_1, phi_1, mass_1);
    auto p2 = ROOT::Math::PtEtaPhiMVector(pt_2, eta_2, phi_2, mass_2);
    return (p1 + p2).M();
}
''')


# Compute the invariant mass with the function jitted above
def compute_mass(df):
    return df.Define('mass', 'computeInvariantMass(goodMuon_pt[idxs[0]], goodMuon_eta[idxs[0]], goodMuon_phi[idxs[0]], goodMuon_mass[idxs[0]], goodTau_pt[idxs[1]], goodTau_eta[idxs[1]], goodTau_phi[idxs[1]], goodTau_mass[idxs[1]])')


# Add the event weights based on the sample being simulation or data
def event_weight(df, sample, xsec, num_events, lumi=1.1 * 1000):
    if 'Run2012' in sample:
        return df.Define('weight', '1.0')
    else:
        return df.Define('weight', '{} * {} / {}'.format(lumi, xsec, num_events))


# Main analysis loop over all samples with reading the info from metadata.csv and plotting
def main():
    # Read sample names, xsecs and number of events per sample
    samples = []
    with open('metadata.csv') as f:
        for line in f.readlines()[1:]:
            sample, xsec, num = line.strip().split(',')
            print('Sample {}: {}, {}'.format(sample, xsec, num))
            samples.append((sample, float(xsec), float(num)))

    # Run analysis
    hists = []
    for sample, xsec, num_events in samples:
        df = ROOT.RDataFrame('Events', 'samples/' + sample + '.root')
        df = selections(df)
        df = find_pair(df)
        df = compute_mass(df)
        df = event_weight(df, sample, xsec, num_events)
        h = df.Histo1D(('', '', 20, 20, 120), 'mass', 'weight')
        hists.append(h)

    # Enable running the event loops concurrently, requires ROOT 6.24
    # ROOT.RDF.RunGraphs(hists)

    # Plot
    data = None
    mc = None
    for hist, (sample, _, _) in zip(hists, samples):
        if 'Run2012' in sample:
            if not data:
                data = hist.GetValue()
            else:
                data.Add(hist.GetValue(), 1.0)
        else:
            if not mc:
                mc = hist.GetValue()
            else:
                mc.Add(hist.GetValue(), 1.0)

    ROOT.gStyle.SetOptStat(0)
    c = ROOT.TCanvas('c', '', 600, 600)
    data.Draw('E1P')
    data.GetXaxis().SetTitle('Visible di-tau mass / GeV')
    data.GetYaxis().SetTitle("N_{Events}")
    mc.Draw('HIST SAME')
    c.SaveAs('plot.png')


if __name__ == '__main__':
    main()
