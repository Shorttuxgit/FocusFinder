package com.glorboflorbo.focusfinderwatch

import android.graphics.Bitmap
import android.os.Bundle
import android.util.Log
import android.view.View
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.AndroidViewModel
import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Delete
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import org.json.JSONArray
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.GregorianCalendar
import org.json.JSONObject
import androidx.lifecycle.viewModelScope
import android.app.Application
import android.content.Context
import androidx.lifecycle.LiveData
import androidx.lifecycle.ViewModelProvider
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import kotlinx.coroutines.launch
import com.google.gson.Gson
import kotlinx.coroutines.sync.Mutex
import org.mozilla.geckoview.AllowOrDeny
import org.mozilla.geckoview.GeckoResult
import org.mozilla.geckoview.GeckoRuntime
import org.mozilla.geckoview.GeckoRuntimeSettings
import org.mozilla.geckoview.GeckoSession
import org.mozilla.geckoview.GeckoView
import org.mozilla.geckoview.WebExtension
import java.lang.Integer.min

class timetable_event
{
    var time_start : GregorianCalendar = GregorianCalendar();
    var time_end : GregorianCalendar = GregorianCalendar();
    var title = "";
    var room = "";
    var staff = "";
    constructor(ts : GregorianCalendar, te : GregorianCalendar, ti : String, ro : String, st : String)
    {
        time_start = ts;
        time_end = te;
        title = ti;
        room = ro;
        staff = st;
    }
}
class timetable_day
{
    var day_of_week : Int;
    var desc_sdfmt = SimpleDateFormat("HH:mm");
    var events = arrayOfNulls<timetable_event>(4);
    constructor(dow : Int)
    {
        day_of_week = dow;
    }
    fun add_ev(ev : timetable_event)
    {
        when(ev.time_start.get(Calendar.HOUR_OF_DAY))
        {
            8 -> events[0] = ev;
            10 -> events[1] = ev;
            12 -> events[2] = ev;
            14 -> events[3] = ev;
            else ->
            {
                return;
            }
        }
    }
    fun describe() : String
    {
        var se : String = "";
        for(i in 0 until 4)
        {
            var ev = events[i]!!;
            var str_b = desc_sdfmt.format(ev.time_start.getTime());
            var str_a = desc_sdfmt.format(ev.time_end.getTime());
            var s = "${str_b}@${str_a}@${ev.title}@${ev.room}@${ev.staff};";
            se += s;
        }
        return se;
    }
    fun interpret(s : String)
    {
        var list = s.split(";");
        for(i in 0 until list.size)
        {
            var ev = list[i];

            try {

                var data = ev.split("@");

                var ts = data[0];
                var te = data[1];
                var title = data[2];
                var room = data[3];
                var staff = data[4];

                var ts_date = (desc_sdfmt.parse(ts));
                var te_date = (desc_sdfmt.parse(te));

                var time_start = GregorianCalendar();
                var time_end = GregorianCalendar();

                time_start.time = ts_date;
                time_end.time = te_date;

                add_ev(timetable_event(time_start, time_end, title, room, staff));
            }
            catch(e : IndexOutOfBoundsException)
            {

            }
        }
    }
}
@Entity
data class week_day
(
    @PrimaryKey val week_day : Int,
    @ColumnInfo val week_day_data : String,
)
data class week_day_list
(
    var day_list : List<week_day>,
)
@Entity
data class week_cached
(
    @PrimaryKey val week_id : Int,
    @ColumnInfo val week_days : week_day_list,
)

class week_list_converter
{
    @TypeConverter
    fun week_list_to_json(wlist : week_day_list): String = Gson().toJson(wlist)
    @TypeConverter
    fun json_to_week_list(str : String): week_day_list = Gson().fromJson(str,week_day_list::class.java)
}

@Dao
interface week_dao
{
    @Query("SELECT * FROM week_cached")
    fun get_all() : LiveData<List<week_cached>>;
    @Query("SELECT * FROM week_cached WHERE week_id IN (:week_ids)")
    fun get_by_week(week_ids : IntArray) : List<week_cached>;

    @Insert
    suspend fun insert_week(vararg week_days : week_cached);

    @Delete
    suspend fun delete_week(week_day : week_cached);
    @Query("DELETE FROM week_cached")
    suspend fun delete_all();
}
@TypeConverters(value = [week_list_converter::class])
@Database(entities = [week_cached::class], version = 1, exportSchema = false)
abstract class week_database : RoomDatabase()
{
    abstract fun get_week_dao() : week_dao;
    companion object
    {
        @Volatile
        private var INSTANCE : week_database? = null;
        fun get_database(ctx : Context) : week_database
        {
            return INSTANCE ?: synchronized(this)
            {
                val instance = Room.databaseBuilder(ctx.applicationContext, week_database::class.java, "week_database").build();
                INSTANCE = instance;
                instance;
            }
        }
    }
}

class week_repo(private val dao : week_dao)
{
    val weeks = dao.get_all();
    suspend fun insert(todo: week_cached) = dao.insert_week(todo)
    suspend fun delete_all() = dao.delete_all();
}

class week_view(application: Application) : AndroidViewModel(application)
{
    private val caches : week_repo;
    val all_weeks : LiveData<List<week_cached>>

    init
    {
        val dao = week_database.get_database(application).get_week_dao();
        caches = week_repo(dao);
        all_weeks = caches.weeks;
    }

    fun insert(week : week_cached) = viewModelScope.launch {
        caches.insert(week);
    }
    fun clear_all() = viewModelScope.launch {
        caches.delete_all()
    }
}

class timetable_view
{
    var vtitle : TextView;
    var vroom : TextView;
    var vtime : TextView;
    var vstaff : TextView;
    var sdfmt : SimpleDateFormat = SimpleDateFormat("HH:mm");
    constructor(vt : TextView, vr : TextView, vs : TextView, vtl : TextView)
    {
        vstaff = vs;
        vtitle = vtl;
        vroom = vr;
        vtime = vt;
    }
    fun set_info(ev: timetable_event)
    {
        var str_b = sdfmt.format(ev.time_start.getTime());
        var str_a = sdfmt.format(ev.time_end.getTime());
        var str_c = "$str_b - $str_a";

        vtime.text = str_c;

        vroom.text = "room: ${ev.room}";
        vtitle.text = "${ev.title}";
        vstaff.text = "staff: ${ev.staff}";
    }
}
class focus_inject
{
    var focus_m : focus_main;
    constructor(fm : focus_main)
    {
        focus_m = fm;
    }
    @JavascriptInterface
    fun handle_post(url : String, body : String)
    {
        Log.println(Log.DEBUG, "dbg", "got post from $url");
        focus_m.lbody = body;
        focus_m.load_timetable();
    }
}
class focus_main : AppCompatActivity() {
    var date : GregorianCalendar = GregorianCalendar();
    var cookies : String? = null;
    var sdfmt4 : SimpleDateFormat = SimpleDateFormat("EEEE, dd'th' MMMM yyyy");
    var sdfmt3 : SimpleDateFormat = SimpleDateFormat("EEEE, dd'rd' MMMM yyyy");
    var sdfmt2 : SimpleDateFormat = SimpleDateFormat("EEEE, dd'nd' MMMM yyyy");
    var sdfmt1 : SimpleDateFormat = SimpleDateFormat("EEEE, dd'st' MMMM yyyy");
    var json_sdf : SimpleDateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    var days = arrayOfNulls<timetable_day>(6);
    var views = arrayOfNulls<timetable_view>(4);
    var lbody : String? = null;
    var nulltimetable_day : timetable_day? = null;
    var cache_view : week_view? = null;
    var port : WebExtension.Port? = null;
    fun update_texts()
    {
        var d = date.get(Calendar.DAY_OF_WEEK) - 2;
        var day : timetable_day?;
        if(d < 0)
            day = nulltimetable_day;
        else
            day = days[d];

        for(i in 0..3)
        {
            Log.println(Log.DEBUG, "dbg", "$i has ${views[i]} with day ${day}");
            views[i]?.set_info(day?.events[i]!!);
        }

    }
    fun update_timetable(events: JSONArray)
    {
        for(i in 0 until 6)
        {
            days[i] = timetable_day(i);
        }
        Log.println(Log.DEBUG, "dbg", "update_timetable with events");
        for(i in 0 until events.length())
        {
            var ev = events.getJSONObject(i);

            var start_raw = ev.getString("start");
            var end_raw = ev.getString("end");

            var clean_start : String;
            var clean_end : String;

            var dt_start : GregorianCalendar = GregorianCalendar();
            var dt_end : GregorianCalendar = GregorianCalendar();

            var day = 0;

            try
            {
                clean_start = start_raw.split(".")[0].replace('T', ' ');
                clean_end = end_raw.split(".")[0].replace('T', ' ');

                dt_start.time = json_sdf.parse(clean_start)!!;

                dt_end.time = json_sdf.parse(clean_end)!!;

                day = dt_start.get(Calendar.DAY_OF_WEEK) - 2;
                if(day < 0)
                    throw Error();

            }
            catch(e : Error)
            {
                continue;
            }
            var title = ev.optString("title", "N/A");
            var room = ev.optString("room", "—");
            var staff = ev.optString("staff", "—");

            if(room == "null")
                room = "—";

            room = room.trim();
            if(room.length <= 0)
                room = "—";
            staff = staff.trim();
            if(staff.length <= 0)
                staff = "—";

            Log.println(Log.DEBUG, "dbg", "got event $title, $room, $staff")
            days[day]?.add_ev(timetable_event(dt_start, dt_end, title, room, staff));
        }

        cache_view?.clear_all();

        val g : GregorianCalendar = GregorianCalendar();
        var wlist : week_day_list = week_day_list(emptyList());
        for(i in 0 until 6)
        {
            val day = days[i];
            val wd : week_day = week_day(i, day?.describe()!!);
            wlist.day_list = wlist.day_list + wd;
        }

        var cache_save = week_cached(g.get(Calendar.WEEK_OF_YEAR), wlist);

        cache_view?.insert(cache_save);

        runOnUiThread {
            var tview = findViewById<TextView>(R.id.view7);
            var button2 = findViewById<Button>(R.id.button2);
            var button1 = findViewById<Button>(R.id.button);
            var button3 = findViewById<Button>(R.id.button3);
            var dm = date.get(Calendar.DAY_OF_MONTH);
            var sdfmt = when (dm % 10) {
                1 -> sdfmt1;
                2 -> sdfmt2;
                3 -> sdfmt3;
                else -> {
                    sdfmt4; }
            }
            if (dm >= 11 && dm <= 13)
                sdfmt = sdfmt4;
            val s = sdfmt.format(date.getTime());
            tview.text = s;
            button2.setOnClickListener {
                date.add(Calendar.DATE, -1);
                var dm = date.get(Calendar.DAY_OF_MONTH);
                var sdfmt = when (dm % 10) {
                    1 -> sdfmt1;
                    2 -> sdfmt2;
                    3 -> sdfmt3;
                    else -> {
                        sdfmt4; }
                }
                if (dm >= 11 && dm <= 13)
                    sdfmt = sdfmt4;
                val s = sdfmt.format(date.getTime());
                tview.text = s;
                update_texts();
            }
            button1.setOnClickListener {
                date.add(Calendar.DATE, 1);
                var dm = date.get(Calendar.DAY_OF_MONTH);
                var sdfmt = when (dm % 10) {
                    1 -> sdfmt1;
                    2 -> sdfmt2;
                    3 -> sdfmt3;
                    else -> {
                        sdfmt4; }
                }
                if (dm >= 11 && dm <= 13)
                    sdfmt = sdfmt4;
                val s = sdfmt.format(date.getTime());
                tview.text = s;
                update_texts();
            }
            button3.setOnClickListener {
                date = GregorianCalendar();
                var dm = date.get(Calendar.DAY_OF_MONTH);
                var sdfmt = when (dm % 10) {
                    1 -> sdfmt1;
                    2 -> sdfmt2;
                    3 -> sdfmt3;
                    else -> {
                        sdfmt4; }
                }
                if (dm >= 11 && dm <= 13)
                    sdfmt = sdfmt4;
                val s = sdfmt.format(date.getTime());
                tview.text = s;
                update_texts();
            }
            update_texts();
        }
    }
    fun load_timetable()
    {
        if(lbody == null)
            return;

        runOnUiThread{

            try {
                var json_obj = JSONObject(lbody!!);
                var jlist_1 = json_obj.getJSONArray("components");
                for (i in 0 until jlist_1.length()) {
                    var jo = jlist_1.getJSONObject(i);
                    var v2 = jo.getJSONObject("effects");
                    var v3 = v2.getJSONArray("dispatches");
                    for (j in 0 until v3.length()) {
                        var v4 = v3.getJSONObject((j));
                        //Log.println(Log.DEBUG, "dbg3", "name: ${(v4.getJSONObject("name").getString())}");
                        if (v4.getString("name") == "event-changed") {
                            var v5 = v4.getJSONObject("params");
                            var v6 = v5.getJSONArray("events");
                            update_timetable(v6);
                        }
                    }
                }
            } catch (e: Error) {
                Log.println(Log.DEBUG, "dbge", e.toString());
            }
        }
    }
    fun init_login()
    {
        setContentView(R.layout.activity_focus_main);

        views[0] = timetable_view(findViewById<TextView>(R.id.v1time), findViewById<TextView>(R.id.v1room), findViewById<TextView>(R.id.v1staff), findViewById<TextView>(R.id.v1title));
        views[1] = timetable_view(findViewById<TextView>(R.id.v2time), findViewById<TextView>(R.id.v2room), findViewById<TextView>(R.id.v2staff), findViewById<TextView>(R.id.v2title));
        views[2] = timetable_view(findViewById<TextView>(R.id.v3time), findViewById<TextView>(R.id.v3room), findViewById<TextView>(R.id.v3staff), findViewById<TextView>(R.id.v3title));
        views[3] = timetable_view(findViewById<TextView>(R.id.v4time), findViewById<TextView>(R.id.v4room), findViewById<TextView>(R.id.v4staff), findViewById<TextView>(R.id.v4title));

        var c1 = GregorianCalendar(0,0,0,8,45);
        var c2 = GregorianCalendar(0,0,0,10,15);

        var c3 = GregorianCalendar(0,0,0,10,30);
        var c4 = GregorianCalendar(0,0,0,12,0);

        var c5 = GregorianCalendar(0,0,0,12,45);
        var c6 = GregorianCalendar(0,0,0,14,15);

        var c7 = GregorianCalendar(0,0,0,14,30);
        var c8 = GregorianCalendar(0,0,0,16,0);

        nulltimetable_day = timetable_day(6);
        nulltimetable_day?.add_ev(timetable_event(c1, c2, "Study Period", "—", "—"));
        nulltimetable_day?.add_ev(timetable_event(c3, c4, "Study Period", "—", "—"))
        nulltimetable_day?.add_ev(timetable_event(c5, c6, "Study Period", "—", "—"))
        nulltimetable_day?.add_ev(timetable_event(c7, c8, "Study Period", "—", "—"))
    }
    fun finish_login()
    {
        init_login();

        /*var webview = findViewById<WebView>(R.id.web2);

        webview.settings.javaScriptEnabled = true;
        webview.settings.domStorageEnabled = true;

        webview.addJavascriptInterface(focus_inject(this), "AndroidFocusInjection");

        var url_target = "https://focus.barton.ac.uk";

        webview.webViewClient = object : WebViewClient()
        {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                if(url == null)
                    return;
                if(!url.contains("timetable"))
                    return;

                Log.println(Log.DEBUG, "dbg2", "Got ON PAGE STARTED");
                view?.evaluateJavascript("(function() {const original_fetch = window.fetch; window.fetch = async (...args) => {const [url, options] = args; const response = await original_fetch(...args); if(options && options.method && options.method == 'POST') { try {const c = response.clone(); const url = c.url; const body = await c.text(); AndroidFocusInjection.handle_post(url, body); } catch (e) {} } return response; }; } )();", null);
            }
            override fun onPageFinished(view: WebView?, url: String?)
            {
                super.onPageFinished(view, url);
                if(url == null)
                    return;
                if(url == url_target)
                    return;
                if(url.contains("timetable"))
                    return;

                var url_got = url;
                Log.println(Log.DEBUG, "dbg", url_got);
                var idx = url.indexOfLast {
                    it == '/'
                }
                if(idx < 0)
                    return;

                var url_timetable = url.subSequence(0, idx+1).toString() + "timetable";
                Log.println(Log.DEBUG, "dbg", url_timetable);

                view?.loadUrl(url_timetable);
            }
        }
        CookieManager.getInstance().setCookie(url_target, cookies);
        webview.loadUrl(url_target);*/

    }
    fun load_gecko()
    {
        var gecko_view : GeckoView = findViewById<GeckoView>(R.id.geckoview);

        var gecko_session : GeckoSession = GeckoSession();

        var gecko_runtime : GeckoRuntime = GeckoRuntime.create(this);
        gecko_runtime.settings.consoleOutputEnabled = true;
        //gecko_session.loadUri("https://focus.barton.ac.uk");
        gecko_session.settings.allowJavascript = true;

        val port_delegate = object : WebExtension.PortDelegate {
            override fun onPortMessage(message: Any, port: WebExtension.Port) {
                super.onPortMessage(message, port)

                lbody = message.toString();

                runOnUiThread {
                    gecko_view.let {
                        gecko_view.releaseSession()?.close();
                    };
                    gecko_session.close();

                    init_login();

                    Log.println(Log.DEBUG,"tag", "lbody: ${lbody}");

                    load_timetable();
                }
            }
        }

        val message_delegate = object : WebExtension.MessageDelegate {
            override fun onConnect(port: WebExtension.Port) {
                super.onConnect(port);
                //Log.println(Log.DEBUG, "ttt", "onConnect");
                port.setDelegate(port_delegate);
            }
        }

        gecko_session.permissionDelegate = object : GeckoSession.PermissionDelegate {
            override fun onContentPermissionRequest(
                session: GeckoSession,
                perm: GeckoSession.PermissionDelegate.ContentPermission
            ): GeckoResult<Int>? {
                return super.onContentPermissionRequest(session, perm)
            }
        }

        gecko_runtime.webExtensionController.list().accept {
                list_ext ->
            val builtInExtensions = list_ext?.filter {
                it.location.startsWith("resource://")
            } ?: emptyList()

            if(builtInExtensions.isEmpty())
            {
                gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/bingus/", "inject@slungomatic.com")
                    .accept { extension -> extension?.setMessageDelegate( message_delegate, "browser");continue_login(gecko_runtime, gecko_session, gecko_view);
                    };
            }
            else
            {
                val uninstallTasks = builtInExtensions.map { extension ->
                    gecko_runtime.webExtensionController.uninstall(extension)
                }
                GeckoResult.allOf(uninstallTasks).accept {
                    gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/fuckingwork/", "inject@slungomatic.com")
                        .accept { extension -> extension?.setMessageDelegate(message_delegate, "browser");continue_login(gecko_runtime, gecko_session, gecko_view);
                        };
                }
            }
        }
    }
    fun load_cache(week: week_cached?) : Boolean
    {
        Log.println(Log.DEBUG, "tg", "week: ${week}");
        if(week == null) {
            load_gecko();
            return false;
        }
        init_login();

        for(i in 0 until 6)
        {
            days[i] = timetable_day(i);
        }
        val len = min(week.week_days.day_list.size, 6);
        for(i in 0 until len)
        {
            val week = week.week_days.day_list[i];

            Log.println(Log.DEBUG, "dbgp", "${week.week_day_data}")

            days[week.week_day]?.interpret(week.week_day_data);
        }

        runOnUiThread {
            var tview = findViewById<TextView>(R.id.view7);
            var button2 = findViewById<Button>(R.id.button2);
            var button1 = findViewById<Button>(R.id.button);
            var button3 = findViewById<Button>(R.id.button3);
            var dm = date.get(Calendar.DAY_OF_MONTH);
            var sdfmt = when(dm % 10)
            {
                1 -> sdfmt1;
                2 -> sdfmt2;
                3 -> sdfmt3;
                else -> {sdfmt4;}
            }
            if(dm >= 11 && dm <= 13)
                sdfmt = sdfmt4;
            val s = sdfmt.format(date.getTime());
            tview.text = s;
            button2.setOnClickListener {
                date.add(Calendar.DATE, -1);
                var dm = date.get(Calendar.DAY_OF_MONTH);
                var sdfmt = when(dm % 10)
                {
                    1 -> sdfmt1;
                    2 -> sdfmt2;
                    3 -> sdfmt3;
                    else -> {sdfmt4;}
                }
                if(dm >= 11 && dm <= 13)
                    sdfmt = sdfmt4;
                val s = sdfmt.format(date.getTime());
                tview.text = s;
                update_texts();
            }
            button1.setOnClickListener {
                date.add(Calendar.DATE, 1);
                var dm = date.get(Calendar.DAY_OF_MONTH);
                var sdfmt = when(dm % 10)
                {
                    1 -> sdfmt1;
                    2 -> sdfmt2;
                    3 -> sdfmt3;
                    else -> {sdfmt4;}
                }
                if(dm >= 11 && dm <= 13)
                    sdfmt = sdfmt4;
                val s = sdfmt.format(date.getTime());
                tview.text = s;
                update_texts();
            }
            button3.setOnClickListener {
                date = GregorianCalendar();
                var dm = date.get(Calendar.DAY_OF_MONTH);
                var sdfmt = when(dm % 10)
                {
                    1 -> sdfmt1;
                    2 -> sdfmt2;
                    3 -> sdfmt3;
                    else -> {sdfmt4;}
                }
                if(dm >= 11 && dm <= 13)
                    sdfmt = sdfmt4;
                val s = sdfmt.format(date.getTime());
                tview.text = s;
                update_texts();
            }
            update_texts();
        }
        return true;
    }
    fun continue_login(gecko_runtime : GeckoRuntime, gecko_session : GeckoSession, gecko_view : GeckoView)
    {
        var url_cur = "";

        gecko_session.navigationDelegate = object : GeckoSession.NavigationDelegate {
            override fun onLocationChange(session: GeckoSession, url: String?) {
                super.onLocationChange(session, url)
                if(url == null)
                    return;
                url_cur = url;
                Log.println(Log.DEBUG, "cng", url);
            }
        }

        gecko_session.progressDelegate = object : GeckoSession.ProgressDelegate {
            override fun onPageStart(session: GeckoSession, url: String)
            {
                super.onPageStart(session, url);
                url_cur = url;
                Log.println(Log.DEBUG, "ondbg", url_cur);
            }

            override fun onPageStop(session: GeckoSession, success: Boolean)
            {
                super.onPageStop(session, success)
                Log.println(Log.DEBUG, "dbg", url_cur);

                if(url_cur.contains("home"))
                {
                    var url_got = url_cur;
                    Log.println(Log.DEBUG, "dbg", url_got);
                    var idx = url_cur.indexOfLast {
                        it == '/'
                    }
                    if(idx < 0)
                        return;

                    var url_timetable = url_cur.subSequence(0, idx+1).toString() + "timetable";
                    Log.println(Log.DEBUG, "dbg", url_timetable);

                    session.loadUri(url_timetable);
                }
            }
        }

        gecko_session.open(gecko_runtime);
        gecko_view.setSession(gecko_session);

        gecko_session.loadUri("https://focus.barton.ac.uk");
    }
    fun do_login()
    {
        var gcur = GregorianCalendar();
        var week_id = gcur.get(Calendar.WEEK_OF_YEAR);
        var has_data = false;
        cache_view?.all_weeks?.observe(this) {
            caches_week -> has_data = load_cache(caches_week.find {
                it.week_id == week_id
            });
        };
        //mutex.lock();
        //if(has_data)
            return;

        //gecko_runtime.on

        /*var webview = findViewById<WebView>(R.id.web);
        webview.alpha = 1.0f;

        webview.settings.javaScriptEnabled = true;
        webview.settings.domStorageEnabled = true;

        var url_target = "https://focus.barton.ac.uk";

        webview.webViewClient = object : WebViewClient()
        {
            override fun onPageFinished(view : WebView?, url : String?)
            {
                super.onPageFinished(view, url);
                if(url != "https://focus.barton.ac.uk/login")
                {
                    var cookies_ = CookieManager.getInstance().getCookie(url);
                    if(cookies_ != null && cookies_.contains("session"))
                    {
                        cookies = cookies_;
                        webview.visibility = View.GONE;
                        Log.println(Log.DEBUG, "dbg", "page finished $url");
                        finish_login();
                    }
                }
            }
        }
        webview.loadUrl(url_target);*/
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cache_view = ViewModelProvider(this)[week_view::class.java];
        enableEdgeToEdge()
        setContentView(R.layout.activity_focus_get)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        do_login();
        /*
        days[0] = timetable_day(timetable_event(c1, c2, "Study Period", "-", "-"),
            timetable_event(c3, c4, "Computer Science - A Level", "N70", "-"),
            timetable_event(c5, c6, "Maths with Further Maths", "N52", "-"),
            timetable_event(c7, c8, "Study Period", "-", "-")
            );

        for(i in 1..5)
        {
            days[i] = days[0];
        }

        var tview = findViewById<TextView>(R.id.view7);
        var button2 = findViewById<Button>(R.id.button2);
        var button1 = findViewById<Button>(R.id.button);
        val s = sdfmt.format(date.getTime());
        tview.text = s;
        button2.setOnClickListener {
            date.add(Calendar.DATE, -1);
            val s = sdfmt.format(date.getTime());
            tview.text = s;
            update_texts();
        }
        button1.setOnClickListener {
            date.add(Calendar.DATE, 1);
            val s = sdfmt.format(date.getTime());
            tview.text = s;
            update_texts();
        }
        update_texts();*/
    }
}