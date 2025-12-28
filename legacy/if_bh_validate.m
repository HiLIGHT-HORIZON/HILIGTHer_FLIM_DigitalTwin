function err = if_bh_validate(img, TCSPC)
    m1 = max(max(sumch(img(:,:,1,:),[4])))
    m2 = max(max(sumch(img(:,:,2,:),[4])))
    
    m = max([m1 m2]);
    
    collection_time = if_lifetime_bhpar(TCSPC,'SP_COL_T');
    
    pixels = if_lifetime_bhpar(TCSPC,'SP_IMG_Y')*if_lifetime_bhpar(TCSPC,'SP_IMG_X');
    
    maxcountrate = m*pixels/collection_time;


    display([mfilename '> Estimated max countrate ' num2str(maxcountrate)])
    
    if maxcountrate>700000
        err = 1;
    else
        err = 0;
    end
    