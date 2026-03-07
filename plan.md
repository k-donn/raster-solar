1.  Refine tile generation
-   [x] One script that accepts timezones + timezone-info and outputs geojson ready for gen
-   [x] Final file will have reference meridian, normal offset, dst offset, and tzid
-   [x] Generate tiles for normal offset
-   [x] Generate tiles for dst offset
2. Statistics generation
-   [x] Calculate average difference between solar noon and local noon within polygon (should be in script?) for dst and non-dst
-   [x] Calculate balancing of timezone?
3.  Display
-   [x] Map has base layer
-   [x] Map has colored tz layer and switcher between dst and non-dst
-   [x] Can hover over a polygon and see tzid, offset, dst offset, and avg. diff between solar noon and local noon
-   [x] Can click on a point and see above info and full EoT for non-dst and dst
3b. Corrects
-   [x] Make all numbers mean the same thing when talking about (solar noon - local noon) => negative means solar noon before. To find solar noon add diff + local noon = solar noon
-   [x] Add description information to values
-   [x] Calculate real-world average offset that accounts for std and dst time
4.  Additional
-   [ ] Highlight which areas do/not use DST
5.  Improvements
-   [ ] Calculate mean diff by land area
-   [ ] Handle overlapping zones