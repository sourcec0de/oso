use polar_core::traces::{CoasterTrace, TraceEvent};
use raylib;
use raylib::consts::KeyboardKey;
use raylib::prelude::*;
use std::fs::File;
use std::io::{prelude, Read};

fn main() {
    // load in the dumped trace data
    let filename = "coaster.json";
    println!("Loading {}", filename);
    let mut file = File::open(filename).unwrap();
    let mut contents = String::new();
    file.read_to_string(&mut contents).unwrap();
    let trace: CoasterTrace = serde_json::from_str(&contents).unwrap();

    let height = trace.max_depth;
    let mut width = 0;

    // todo: need to add results so I can know which paths are successful

    // track how many points we have for each level.
    let mut num_in_level = vec![0; trace.max_depth+1];
    // try to figure out path by keeping track of where we branched from
    let mut last_in_level = vec![0; trace.max_depth+1];
    let mut current_level = 0;
    let mut edges = vec![];
    // path from the root to where we are
    let mut pos = vec![];
    // path the cart travels including backtracking
    let mut cart_path = vec![0];
    for (i, depthp) in trace.depths.iter().enumerate() {
        let depth = *depthp;
        num_in_level[depth] += 1;
        width = std::cmp::max(width, num_in_level[depth]);

        if i == 0 {
            assert_eq!(depth, 0);
            continue;
        }

        if depth == current_level {
            edges.push((last_in_level[depth], i));
        } else if depth >= current_level {
            assert_eq!(depth, current_level+1);
            edges.push((last_in_level[current_level], i));
        } else if depth < current_level {
            let backtrack_to = last_in_level[depth-1];
            edges.push((backtrack_to, i));

            // backtrack
            pos.pop();
            while let Some(x) = pos.pop() {
                cart_path.push(x);
                if x == backtrack_to {
                    pos.push(x);
                    break
                }
            }
        }

        last_in_level[depth] = i;
        pos.push(i);
        cart_path.push(i);
        current_level = depth;
    }

    let mut node_positions = vec![Vector2::default(); trace.depths.len()];
    let mut seen_at_level = vec![0; trace.max_depth+1];
    for (i, depthp) in trace.depths.iter().enumerate() {
        let depth = *depthp;
        let offset = (width-1 - (num_in_level[depth]-1)) as f32 / 2.0;
        node_positions[i].x = seen_at_level[depth] as f32 + offset;
        node_positions[i].y = depth as f32;
        seen_at_level[depth] += 1;
    }

    // scale the thing to fit in the window. Not going to look good for really big or really
    // small traces but can handle that later.
    let window_width = 960 as f32;
    let window_height = 540 as f32;

    let width = (width-1) as f32;
    let height = (height) as f32;

    let scale = Vector2{
        x: window_width*0.6 / width,
        y: window_height*0.8 / height
    };

    let offset = Vector2{
        x: (window_width - (width * scale.x)) / 2.0,
        y: (window_height - (height * scale.y)) / 2.0
    };

    // scale node positions
    for pos in &mut node_positions {
        *pos = *pos*scale+offset;
    }

    let (mut rl, thread) = raylib::init()
        .size(window_width as i32, window_height as i32)
        .title("Polarcoaster")
        .build();

    let mut cart_from = 0;
    let mut cart_to = 1;
    let mut cart_progress: f32 = 0.0;

    let time_per_node = 1.5;
    let mut last_t = 0.0;

    let mut track_lines = vec![];
    for (fromp, top) in &edges {
        let from = *fromp;
        let to = *top;
        let from_p = node_positions[from];
        let to_p = node_positions[to];
        let path = to_p-from_p;
        // Guide line for debugging
        // track_lines.push((from_p, to_p, 2.0, Color::GREEN));
        let unit = path.normalized();
        let perp = Vector2{
            x: unit.y,
            y: -unit.x
        };
        let offset = perp.scale_by(3.0);
        // outside lines
        track_lines.push((from_p+offset, to_p+offset, 2.0, Color::BLACK));
        track_lines.push((from_p-offset, to_p-offset, 2.0, Color::BLACK));
        // little track bars so it looks like a train
        for percent in [0.25, 0.5, 0.75] {
            let p = from_p + path.scale_by(percent);
            track_lines.push((p-offset, p+offset, 2.0, Color::BLACK));
        }
    }

    while !rl.window_should_close() {
        if rl.is_key_pressed(KeyboardKey::KEY_R) {
            cart_from = 0;
            cart_to = 1;
            cart_progress = 0.0;
        }
        // its not a real simulation so we dont care about consistent time steps
        // just compute how far along the track we are.
        // looks pretty silly because every segment is traveled over the same
        // amount of time even though they arent the same lengths
        let t = rl.get_time();
        let time_passed = t - last_t;
        let frame_progress = (time_passed / time_per_node) as f32;
        cart_progress += frame_progress;
        while cart_progress > 1.0 {
            cart_from = (cart_from + 1) % cart_path.len();
            cart_to = (cart_to + 1) % cart_path.len();
            cart_progress -= 1.0;
        }
        last_t = t;

        let mut d = rl.begin_drawing(&thread);

        d.clear_background(Color::WHITE);
        let p = Vector2::zero()*scale+offset;

        for (start, end, thick, color) in &track_lines {
            d.draw_line_ex(start, end, *thick, color);
        }

        let mousep = Vector2{
            x: d.get_mouse_x() as f32,
            y: d.get_mouse_y() as f32
        };

        let mut mousedraw = false;
        for (i, pos) in node_positions.iter().enumerate() {
            d.draw_circle_v(*pos, 4.0, Color::DARKBLUE);
            if mousep.distance_to(*pos) <= 4.0 {
                mousedraw = true;
                let event = &trace.events[i];
                let text = match event {
                    TraceEvent::Query { term } => {
                        polarfmt(term.to_string())
                    }
                    TraceEvent::Rule { rule } => {
                        rule.to_string()
                    }
                };

                d.draw_text(&text, 12,12,18,Color::BLUE);
            }
        }

        let from_node = cart_path[cart_from];
        let to_node = cart_path[cart_to];
        let cart_start = node_positions[from_node];
        let cart_end = node_positions[to_node];
        let to_next = cart_end - cart_start;
        let cart_pos = cart_start + to_next.scale_by(cart_progress);
        d.draw_circle_v(cart_pos, 6.0, Color::RED);

        if !mousedraw {
            let event = &trace.events[from_node];
            let text = match event {
                TraceEvent::Query { term } => {
                    polarfmt(term.to_string())
                }
                TraceEvent::Rule { rule } => {
                    rule.to_string()
                }
            };

            d.draw_text(&text, 12, 12, 18, Color::BLACK);
        }
    }
}

fn polarfmt(polar: String) -> String {
    polar.split("and").collect::<Vec<&str>>().join("\n  and")
}