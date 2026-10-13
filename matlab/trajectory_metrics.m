function result = trajectory_metrics(inputCsv, outputCsv)
if nargin<2;outputCsv='velocity_matlab.csv';end
T=readtable(inputCsv);
needed={'time_s','x_mm','y_up_mm','detected'};
assert(all(ismember(needed,T.Properties.VariableNames)),'Missing track headers');
n=height(T); assert(n>=2,'At least two records needed');
speed_mm_s=nan(n,1);velocity_x_mm_s=nan(n,1);velocity_up_mm_s=nan(n,1);
for j=2:n
    if T.detected(j) && T.detected(j-1)
        dt=T.time_s(j)-T.time_s(j-1);
        assert(dt>0,'Non-increasing timestamps');
        vx=(T.x_mm(j)-T.x_mm(j-1))/dt;
        vy=(T.y_up_mm(j)-T.y_up_mm(j-1))/dt;
        speed_mm_s(j)=hypot(vx,vy);velocity_x_mm_s(j)=vx;velocity_up_mm_s(j)=vy;
    end
end
result=table(T.time_s,speed_mm_s,velocity_x_mm_s,velocity_up_mm_s,'VariableNames',...
          {'time_s','speed_mm_s','velocity_x_mm_s','velocity_up_mm_s'});
writetable(result,outputCsv);disp(['Saved to ',outputCsv]);
end
