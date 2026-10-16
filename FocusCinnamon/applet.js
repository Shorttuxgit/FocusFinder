const Applet = imports.ui.applet;
const Util = imports.misc.util;
const GLib = imports.gi.GLib;
const Mainloop = imports.mainloop;
const ByteArray = imports.byteArray; 
const Lang = imports.lang;
const St = imports.gi.St;
const Gio = imports.gi.Gio;
const PopupMenu = imports.ui.popupMenu;
const AppletDir = imports.ui.appletManager.appletMeta['focus@slungus_village'].path;

function MyApplet(orientation, panel_height, instance_id) {
    this._init(orientation, panel_height, instance_id);
}

MyApplet.prototype = {
      __proto__: Applet.IconApplet.prototype,

      _run_cmd: function(cmd)
      {
            try
            {
                  let [result, pid, stdin, stdout, stderr] = GLib.spawn_async_with_pipes(AppletDir, [cmd], null, GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD, null);
                  if(!result)
                        return;
                  if (stdin > 0) GLib.close(stdin);
                  if (stderr > 0) GLib.close(stderr);
                  let stdoutStream = new Gio.UnixInputStream({ fd: stdout, close_fd: true });
                  GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, (child_pid, status) => {
                        stdoutStream.read_bytes_async(8192, GLib.PRIORITY_DEFAULT, null, (stream, res) => {
                              try
                              {
                                    let gbytes = stream.read_bytes_finish(res);
                                    if(gbytes)
                                    {
                                          let json_raw = ByteArray.toString(gbytes.toArray());
                                          json_raw.trim();
                                          
                                          if(json_raw)
                                          {
                                                let json_obj = json_raw.split('^')
                                                
                                                let f = json_obj;
                                                
                                                let prev = Number.MAX_SAFE_INTEGER;
                                                
                                                for(let i = 0; i < f.length; i++)
                                                {
                                                      const element = f[i];
                                                      try
                                                      {
                                                            let dates = element.split('$');
                                                            let day_of_year = parseInt(dates[0]);
                                                            
                                                            let cmP_date = new Date();
                                                            let tomorrow = new Date();
                                                            tomorrow.setDate(tomorrow.getDate() + 1);
                                                            if(cmP_date.getHours() >= 8)
                                                                  cmP_date = tomorrow;
                                                            //global.logError(`${dates[0]} time => ${day_of_year} ?= ${Math.trunc(cmP_date.getTime() / (1000*60*60*24))} ${prev}`);
                                                            let today_year = Math.trunc(cmP_date.getTime() / (1000*60*60*24));
                                                            if((day_of_year == today_year) || ((prev < today_year) && (day_of_year > today_year)))
                                                            {
                                                                  let day_date = new Date();
                                                                  day_date.setTime(day_of_year*60*60*24*1000);
                                                                  let str_date = day_date.toLocaleDateString().slice(0, 10).padEnd(10, " ");
                                                                  let str = `--- ${str_date} -------------------------------------------------------\n`;
                                                                  str += "Time              | Event Title                  | Room     | Staff\n";
                                                                  str += "----------------------------------------------------------------------\n";
                                                                  let ev = dates[1].split(';');
                                                                  for(let j = 0; j < ev.length; j++)
                                                                  {
                                                                        let ev_data = ev[j].split('@');
                                                                        if(ev_data.length < 5)
                                                                              continue;
                                                                        let str1 = `${ev_data[0]} - ${ev_data[1]}`
                                                                        let start = str1.slice(0, 17).padEnd(17, " ");
                                                                        let str2 = ev_data[2];
                                                                        let title = str2.slice(0, 28).padEnd(28, " ");
                                                                        let str3 = ev_data[3];
                                                                        let room = str3.slice(0, 8).padEnd(8, " ");
                                                                        let str4 = ev_data[4];
                                                                        str += `${start} | ${title} | ${room} | ${str4}`
                                                                        if(j+1 < ev.length)
                                                                              str += "\n";
                                                                  }
                                                                  
                                                                  let sv_str = "";
                                                                  
                                                                  let sz_max = 0;
                                                                  
                                                                  let list_nl = str.split("\n");
                                                                  for(let j = 0; j < list_nl.length; j++)
                                                                  {
                                                                        let sz = list_nl[j].length;
                                                                        if(sz > sz_max)
                                                                              sz_max = sz;
                                                                  }
                                                                  
                                                                  for(let j = 0; j < list_nl.length; j++)
                                                                  {
                                                                        sv_str += list_nl[j].padEnd(sz_max, " ");
                                                                        if(j+1 < list_nl.length)
                                                                              sv_str += "\n";
                                                                  }
                                                                  
                                                                  this.week_tm = sv_str;
                                                                  this.set_applet_tooltip(this.week_tm);
                                                                  break;
                                                            }
                                                            prev = day_of_year;
                                                      }
                                                      catch (e)
                                                      {
                                                            //global.logError(e);
                                                      }
                                                }
                                          }
                                          
                                    }
                              }
                              catch(e)
                              {
                                    global.logError(e);
                              }
                        });
                        GLib.spawn_close_pid(pid);
                  });
            }
            catch(e)
            {
                  global.logError(e);
            }
            return;
      },
      on_applet_removed_from_panel: function() 
      {
            if(this._updateLoopID)
            {
                  Mainloop.source_remove(this._updateLoopID);
            }
            if(this._updateLoop2ID)
            {
                  Mainloop.source_remove(this._updateLoop2ID);
            }
      },
      
      _update_loop_n1: function()
      {
            this._run_cmd(AppletDir + "/Core.py");
            this._updateLoopID = Mainloop.timeout_add(60*60*2*1000, Lang.bind(this, this._update_loop_n1));
            
      },
      
      on_applet_clicked: function(event) 
      {
            this.menu.toggle();
      },
      
      _update_loop_n2: function()
      {
            this.info_menu_item.label.get_clutter_text().set_markup(this.week_tm, true);
            this._updateLoop2ID = Mainloop.timeout_add(5*1000, Lang.bind(this, this._update_loop_n2));
      },

      _init: function(orientation, panel_height, instance_id) {
        Applet.IconApplet.prototype._init.call(this, orientation, panel_height, instance_id);
            let iconFile = AppletDir + "/" + "icon.svg";

            try {
              this.set_applet_icon_path(iconFile);
              global.log("Set applet icon to: " + iconFile);
            } catch (e) {
              global.logError(e);
            }
            this.menu_manager = new PopupMenu.PopupMenuManager(this);
            this.menu = new Applet.AppletPopupMenu(this, orientation);
            this.menu_manager.addMenu(this.menu);
            this.week_tm = "Getting next day...";
            
            this.info_menu_item = new PopupMenu.PopupMenuItem("Getting next day...", { reactive: false });
            this.menu.addMenuItem(this.info_menu_item);
            this._update_loop_n1();
            this._update_loop_n2();
      },
};

function main(metadata, orientation, panel_height, instance_id) {
      return new MyApplet(orientation, panel_height, instance_id);
}
