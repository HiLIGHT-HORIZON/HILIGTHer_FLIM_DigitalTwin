
clearvars;
clc;

fid = fopen('100x_1\image2D_G0.bin');
G0raw = fread(fid,'uint32');

fid = fopen('100x_1\image2D_G1.bin');
G1raw = fread(fid,'uint32');

fid = fopen('100x_1\image2D_G2.bin');
G2raw = fread(fid,'uint32');

fid = fopen('100x_1\image2D_G3.bin');
G3raw = fread(fid,'uint32');

G0vec = G0raw;
G1vec = G1raw - G0raw;
G2vec = G2raw - G1raw;
G3vec = G3raw - G2raw;

G0 = fliplr(rot90(rot90(rot90(reshape(G0vec,100,100)))));
G1 = fliplr(rot90(rot90(rot90(reshape(G1vec,100,100)))));
G2 = fliplr(rot90(rot90(rot90(reshape(G2vec,100,100)))));
G3 = fliplr(rot90(rot90(rot90(reshape(G3vec,100,100)))));

edge_G0 = 0:1:max(G0raw);
edge_G1 = 0:1:max(G1raw);
edge_G2 = 0:1:max(G2raw);
edge_G3 = 0:1:max(G3raw);

h0 = histcounts(G0raw,edge_G0); h0=h0./sum(h0); c0 = cumsum(h0);
h1 = histcounts(G1raw,edge_G1); h1=h1./sum(h1); c1 = cumsum(h1);
h2 = histcounts(G2raw,edge_G2); h2=h2./sum(h2); c2 = cumsum(h2);
h3 = histcounts(G3raw,edge_G3); h3=h3./sum(h3); c3 = cumsum(h3);

%% filtering parameters

thr = 0.95;

th0 = find(c0>thr,1);
th1 = find(c1>thr,1);
th2 = find(c2>thr,1);
th3 = find(c3>thr,1);
w = 3;

%% thresholding 

G0(G0>th0) = 0;
G1(G1>th1) = 0;
G2(G2>th2) = 0;
G3(G3>th3) = 0;

%% denoising

G0filt = medfilt2(G0, [w w]);
G1filt = medfilt2(G1, [w w]);
G2filt = medfilt2(G2, [w w]);
G3filt = medfilt2(G3, [w w]); 

%% plot
r=1;
c=4;
mapstr = "parula";

subplot(r,c,1);
imshow(G0filt, [min(min(G0filt)) max(max(G0filt))]);
title('G0 with thresholding + median filt');
colormap(mapstr);
pbaspect([1 1 1]);

subplot(r,c,2);
imshow(G1filt, [min(min(G1filt)) max(max(G1filt))]);
title('G1 with thresholding + median filt');
colormap(mapstr);
pbaspect([1 1 1]);

subplot(r,c,3);
imshow(G2filt, [min(min(G2filt)) max(max(G2filt))]);
title('G2 with thresholding + median filt');
colormap(mapstr);
pbaspect([1 1 1]);

subplot(r,c,4);
imshow(G3filt, [min(min(G3filt)) max(max(G3filt))]);
title('G3 with thresholding + median filt');
colormap(mapstr);
pbaspect([1 1 1]);