import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
fig,ax=plt.subplots(figsize=(10,3.5),dpi=150); ax.set_xlim(0,100); ax.set_ylim(0,40); ax.axis('off')
def box(x,y,w,h,txt,fc,ec='#333333',fs=9,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.4,rounding_size=1.2",fc=fc,ec=ec,lw=1.2))
    ax.text(x+w/2,y+h/2,txt,ha='center',va='center',fontsize=fs,weight='bold' if bold else 'normal',wrap=True)
def arrow(x1,y1,x2,y2,txt=None):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=14,lw=1.3,color='#444444'))
    if txt: ax.text((x1+x2)/2,(y1+y2)/2+2.2,txt,ha='center',va='bottom',fontsize=7.5,style='italic',color='#555555')
BL=(0.86,0.90,0.97); GR=(0.90,0.94,0.90); YE=(0.98,0.95,0.82); OR=(0.98,0.90,0.82)
# controversy input (top, feeding into key-issue scores)
box(1,27,20,10,"ESG controversies\n(Moderate / Severe /\nVery severe)",OR,fs=8.5)
# stage boxes along the middle
y=14; h=11
box(1,y,20,h,"Key-issue\nscores",GR)
box(27,y,19,h,"Weighted-average\nkey-issue score\n(WAKIS)",GR)
box(52,y,19,h,"Industry-Adjusted\nScore (IAS, 0\u201310)",BL)
box(78,y,21,h,"Letter rating\nCCC \u2026 AAA\n(6 thresholds)",BL)
arrow(21,19.5,27,19.5,"materiality\nweights")
arrow(46,19.5,52,19.5,"industry\nbenchmarking")
arrow(71,19.5,78,19.5,"6 fixed\nthresholds")
arrow(11,27,11,25.2)  # controversy -> key-issue scores
# annotations under boxes (what we observe/measure)
ax.text(11,12.4,"observed input",ha='center',fontsize=7,color='#1f6f3f',style='italic')
ax.text(36.5,12.4,"published (own-score input)",ha='center',fontsize=7,color='#1f6f3f',style='italic')
ax.text(61.5,12.4,"published outcome (\u0394IAS)",ha='center',fontsize=7,color='#234b8a',style='italic')
ax.text(88.5,12.4,"coarse categories",ha='center',fontsize=7,color='#234b8a',style='italic')
# brace note
ax.text(50,4.5,"Attenuation is measured at each stage: severity-graded response (\u00A76.2), own-score vs non-own-score share at the benchmarking stage (\u00A76.3), and coarseness at the thresholds (\u00A76.2).",
        ha='center',va='center',fontsize=7.6,color='#333333')
fig.tight_layout(); fig.savefig('fig_architecture.png',bbox_inches='tight',dpi=150); print("architecture figure saved")
