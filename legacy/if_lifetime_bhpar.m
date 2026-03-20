%% {header}

function o = if_lifetime_bhpar(s, par_name)
    for i=1:length(s)
       if strcmp(s(i).parameter,par_name) 
          o = s(i).value;
          switch s(i).type
            case {'F','D','U','I','O'}
                o = str2num(o);                           
          end
          break
       end
    end
return