package dev.blockmind.minecraft.navigation;

import dev.blockmind.minecraft.GameAccess.Pos;
import java.util.*;
import java.util.function.Predicate;

/** Bounded, deterministic loaded-cell A*. No chunks are generated or mutated. */
public final class FlightRoutePlanner {
    public record Area(Pos minimum, Pos maximum) {
        public boolean contains(Pos p) {
            return p.x()>=minimum.x() && p.x()<=maximum.x() && p.y()>=minimum.y() && p.y()<=maximum.y()
                && p.z()>=minimum.z() && p.z()<=maximum.z();
        }
    }
    private record Node(Pos position, int cost, int estimate, long order) { }
    private static int distance(Pos a, Pos b) { return Math.abs(a.x()-b.x())+Math.abs(a.y()-b.y())+Math.abs(a.z()-b.z()); }
    public static boolean clear(Pos from, Pos to, Area area, Predicate<Pos> safe) {
        int steps = Math.max(1,distance(from,to)*4);
        if (area==null || steps>1024) return false;
        for (int i=0;i<=steps;i++) {
            double t=(double)i/steps;
            double x=from.x()+.5+(to.x()-from.x())*t, y=from.y()+(to.y()-from.y())*t, z=from.z()+.5+(to.z()-from.z())*t;
            // Full .6-wide body, not only its centre; the predicate includes head clearance.
            for (double dx : new double[]{-.31,.31}) for (double dz : new double[]{-.31,.31}) {
                Pos p=new Pos((int)Math.floor(x+dx),(int)Math.floor(y),(int)Math.floor(z+dz));
                if (!area.contains(p) || !safe.test(p)) return false;
            }
        }
        return true;
    }
    public static List<Pos> route(Pos from, Pos to, Area area, Predicate<Pos> observedSafe, int maximum) {
        if (area==null || maximum<1 || maximum>4096 || !area.contains(from) || !area.contains(to)) return List.of();
        Map<Pos,Boolean> checked=new HashMap<>();
        Predicate<Pos> safe=p -> checked.computeIfAbsent(p,observedSafe::test);
        if (!safe.test(from) || !safe.test(to)) return List.of();
        if (clear(from,to,area,safe)) return List.of(to);
        var open=new PriorityQueue<Node>(Comparator.comparingInt(Node::estimate).thenComparingInt(Node::cost).thenComparingLong(Node::order));
        Map<Pos,Integer> costs=new HashMap<>(); Map<Pos,Pos> previous=new HashMap<>();
        Set<Pos> closed=new HashSet<>(); long order=0;
        open.add(new Node(from,0,distance(from,to),order++)); costs.put(from,0);
        int[][] directions={{0,1,0},{1,0,0},{0,0,1},{-1,0,0},{0,0,-1},{0,-1,0}};
        while (!open.isEmpty() && closed.size()<maximum) {
            Node node=open.remove(); Pos here=node.position();
            if (!closed.add(here)) continue;
            if (here.equals(to)) {
                List<Pos> raw=new ArrayList<>(); for (Pos p=to; !p.equals(from); p=previous.get(p)) raw.add(p);
                Collections.reverse(raw); List<Pos> result=new ArrayList<>(); Pos anchor=from;
                for (int index=0; index<raw.size();) {
                    int end=index;
                    while (end+1<raw.size() && clear(anchor,raw.get(end+1),area,safe)) end++;
                    anchor=raw.get(end); result.add(anchor); index=end+1;
                }
                return List.copyOf(result);
            }
            for (int[] d:directions) {
                Pos next=here.add(d[0],d[1],d[2]); int cost=node.cost()+1;
                if (!area.contains(next) || closed.contains(next) || !safe.test(next) || costs.getOrDefault(next,Integer.MAX_VALUE)<=cost) continue;
                costs.put(next,cost); previous.put(next,here);
                open.add(new Node(next,cost,cost+distance(next,to),order++));
            }
        }
        return List.of(); // Explicit bounded failure, never an unchecked direct flight.
    }
}
