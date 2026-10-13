
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

int main(int argc, char **argv){
    FILE *in,*out; char line[2048]; double t,x,y,pt=0,px=0,py=0; int detected,prev=0; long rows=0;
    if(argc!=3){fprintf(stderr,"Usage: track_velocity input.csv output.csv\n");return 2;}
    in=fopen(argv[1],"r");if(!in){perror("input");return 2;}
    out=fopen(argv[2],"w");if(!out){perror("output");fclose(in);return 2;}
    if(!fgets(line,sizeof(line),in) || strstr(line,"time_s")==NULL){
        fprintf(stderr,"CSV header required\n");fclose(in);fclose(out);return 3;}
    fprintf(out,"time_s,speed_mm_s,vx_mm_s,vy_mm_s\n");
    while(fgets(line,sizeof(line),in)){
        int matched=sscanf(line," %lf , %lf , %lf , %d",&t,&x,&y,&detected);
        if(matched!=4 || !isfinite(t) || (detected!=0 && detected!=1)){
            fprintf(stderr,"Malformed row %ld\n",rows+2);fclose(in);fclose(out);return 4;}
        if(rows>0 && t<=pt){fprintf(stderr,"Timestamps must be strictly increasing\n");fclose(in);fclose(out);return 4;}
        if(detected && (!isfinite(x)||!isfinite(y))){
            fprintf(stderr,"Nonfinite detected position on row %ld\n",rows+2);fclose(in);fclose(out);return 4;}
        if(detected && prev){
            double dt=t-pt,vx=(x-px)/dt,vy=(y-py)/dt;
            fprintf(out,"%.12g,%.12g,%.12g,%.12g\n",t,hypot(vx,vy),vx,vy);
        }else fprintf(out,"%.12g,,,\n",t);
        prev=detected;pt=t;px=x;py=y;rows++;
    }
    fclose(in);fclose(out);
    if(rows<2){fprintf(stderr,"Input needs at least two points\n");return 5;}
    fprintf(stderr,"Processed %ld frames, no gap interpolation\n",rows);
    return 0;
}
