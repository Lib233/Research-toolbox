function [best,score] = optimize_model_fminsearch(objective, bounds, maximize)
if nargin<3;maximize=false;end
assert(isnumeric(bounds) && size(bounds,2)==2 && all(isfinite(bounds(:))) && all(bounds(:,2)>bounds(:,1)),...
    'bounds must be an N-by-2 finite matrix with lower<upper');
lower=bounds(:,1)';span=(bounds(:,2)-bounds(:,1))';
transform=@(z) lower+span./(1+exp(-max(-80,min(80,z))));
signVal=1;if maximize;signVal=-1;end
f=@(z) signVal*objective(transform(z));
opts=optimset('Display','off','MaxFunEvals',6000,'MaxIter',2000,'TolX',1e-8,'TolFun',1e-8);
[z,~,flag]=fminsearch(f,zeros(1,size(bounds,1)),opts);
best=transform(z);score=objective(best);
if flag<=0;warning('Optimization may not have converged');end
end
