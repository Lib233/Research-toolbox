function summary = adhesion_force_batch(inputCsv, outputCsv, contactArea_mm2)
if nargin<3; contactArea_mm2=NaN; end
if nargin<2; outputCsv='force_metrics_matlab.csv'; end
if ~(isnan(contactArea_mm2) || (isscalar(contactArea_mm2) && isfinite(contactArea_mm2) && contactArea_mm2>0))
    error('contactArea_mm2 must be positive or NaN.');
end
T=readtable(inputCsv,'TextType','string');
need={'condition','sample_id','time_s','displacement_mm','force_N'};
assert(all(ismember(need,T.Properties.VariableNames)),'Required headers missing.');
[groups,conditions,samples]=findgroups(string(T.condition),string(T.sample_id));
nG=max(groups); condition=strings(nG,1);sample_id=strings(nG,1);
peak_force_N=zeros(nG,1);displacement_at_peak_mm=zeros(nG,1);
separation_work_mJ=zeros(nG,1);baseline_N=zeros(nG,1);n_points=zeros(nG,1);
peak_nominal_stress_kPa=nan(nG,1);
for g=1:nG
   D=T(groups==g,:);D=sortrows(D,'time_s');
   t=D.time_s;x=D.displacement_mm;f=D.force_N;
   assert(numel(t)>=3 && all(diff(t)>0),'Need strictly increasing time, at least 3 points.');
   assert(all(diff(x)>=-1e-9),'Displacement nonmonotonic: split cycles first.');
   assert(all(isfinite([t;x;f])),'Missing or nonfinite values are not allowed.');
   baseline=median(f(1:max(1,ceil(0.05*numel(f)))));
   tensile=max(0,f-baseline);
   [pk,idx]=max(tensile);
   condition(g)=conditions(g);sample_id(g)=samples(g);
   peak_force_N(g)=pk;displacement_at_peak_mm(g)=x(idx);
   separation_work_mJ(g)=trapz(x,tensile);baseline_N(g)=baseline;n_points(g)=numel(f);
   if ~isnan(contactArea_mm2)
       peak_nominal_stress_kPa(g)=1000*pk/contactArea_mm2;
   end
end
summary=table(condition,sample_id,n_points,baseline_N,peak_force_N,displacement_at_peak_mm,separation_work_mJ,peak_nominal_stress_kPa);
writetable(summary,outputCsv);
disp(summary)
end
