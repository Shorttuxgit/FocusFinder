package com.glorboflorbo.focusfinder

import android.Manifest
import android.annotation.SuppressLint
import android.app.Application
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.drawable.Drawable
import android.graphics.drawable.PictureDrawable
import android.location.Location
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import android.util.Log
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ImageView
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.constraintlayout.widget.ConstraintLayout
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
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
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import com.caverock.androidsvg.SVG
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationServices
import com.google.gson.Gson
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.lang.Integer.min
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.GregorianCalendar
import java.util.Hashtable
import java.util.Locale
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.stream.Collectors
import javax.net.ssl.HttpsURLConnection
import kotlin.concurrent.thread
import kotlin.math.abs

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
            catch(e : Exception)
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
abstract class gesture_swipe : View.OnTouchListener
{
    var gesture_detector : GestureDetector;

    constructor(ctx : Context)
    {
        gesture_detector = GestureDetector(ctx, GestureListener());
    }

    override fun onTouch(p0: View, p1: MotionEvent): Boolean {
        return gesture_detector.onTouchEvent(p1);
    }
    inner class GestureListener : GestureDetector.SimpleOnGestureListener()
    {
        override fun onDoubleTap(e: MotionEvent): Boolean {
            onDoubleClick();
            return true;
        }
        override fun onFling(
            e1: MotionEvent?,
            e2: MotionEvent,
            velocityX: Float,
            velocityY: Float
        ): Boolean {
            var result : Boolean = false;
            try
            {
                val diffY = e2.getY() - e1!!.getY()
                val diffX = e2.getX() - e1.getX()
                if (abs(diffX) > abs(diffY)) {
                    if (abs(diffX) > 100 && Math.abs(velocityX) > 100) {
                        if (diffX > 0) {
                            onSwipeRight()
                        } else {
                            onSwipeLeft()
                        }
                        result = true
                    }
                }
            }
            catch(e : Exception)
            {

            }
            return result;
        }
    }
    abstract fun onSwipeLeft();
    abstract fun onSwipeRight();
    abstract fun onDoubleClick();
}
class weather_day
{
    var min_temp : Double;
    var max_temp : Double;
    var wdraw : Drawable;
    var rainp : Double;
    var is_day : Boolean;
    var today : Boolean;

    constructor(mt : Double, mxt : Double, wb : Drawable, ranp : Double, is_dy : Boolean, t : Boolean)
    {
        min_temp = mt;
        max_temp = mxt;
        wdraw = wb;
        rainp = ranp;
        is_day = is_dy;
        today = t;
    }
    fun is_raining() : Boolean
    {
        return (rainp > 0.01);
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
    var wdays = arrayOfNulls<weather_day>(7);
    var views = arrayOfNulls<timetable_view>(4);
    var lbody : String? = null;
    var web_view : WebView? = null;
    var nulltimetable_day : timetable_day? = null;
    var cache_view : week_view? = null;
    var fusedLocationClient: FusedLocationProviderClient? = null;
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
        update_weather_day();
    }
    fun update_weather_day()
    {
        var d = date.get(Calendar.DAY_OF_WEEK) - 2;
        if(d < 0)
            d = 6;
        var weekd = wdays[d];
        if(weekd == null)
            return;
        //if(weekd.is_raining() || !weekd.is_day)
        //    AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES);
        //else
        //    AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO);
        var weahter = findViewById<TextView>(R.id.weahter);
        var sst : String = "";
        if(weekd.today) {
            if (weekd.is_raining())
                sst += "Rain, ";
            if (weekd.is_day)
                sst += "Day";
            else
                sst += "Night";
        }
        else if (weekd.is_raining())
            sst += "Rain";
        sst += " (${weekd.min_temp}°C - ${weekd.max_temp}°C)"
        weahter.text = sst;
        var iview = findViewById<ImageView>(R.id.imageView);
        iview.setImageDrawable(weekd.wdraw);
    }
    @SuppressLint("ClickableViewAccessibility")
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
                    throw Exception();

            }
            catch(e : Exception)
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
        var week_id = g.get(Calendar.WEEK_OF_YEAR);
        val calendar = Calendar.getInstance(Locale.getDefault())
        val firstDayInt = calendar.getFirstDayOfWeek()
        if(g.get(Calendar.DAY_OF_WEEK) == Calendar.SUNDAY && firstDayInt == Calendar.SUNDAY)
            week_id--;
        var cache_save = week_cached(week_id, wlist);

        cache_view?.insert(cache_save);

        runOnUiThread {
            var tview = findViewById<TextView>(R.id.view7);
            var button2 = findViewById<Button>(R.id.button2);
            var button1 = findViewById<Button>(R.id.button);
            var button3 = findViewById<Button>(R.id.button3);
            var scv = findViewById<ScrollView>(R.id.scroll_view);
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
                if(date.get(Calendar.DAY_OF_WEEK) != Calendar.MONDAY) {
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
            }
            button1.setOnClickListener {
                if(date.get(Calendar.DAY_OF_WEEK) != Calendar.SUNDAY) {
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

            scv.setOnTouchListener(object : gesture_swipe(this) {
                override fun onSwipeRight() {
                    if(date.get(Calendar.DAY_OF_WEEK) != Calendar.MONDAY) {
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
                }

                override fun onDoubleClick() {
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

                override fun onSwipeLeft() {
                    if(date.get(Calendar.DAY_OF_WEEK) != Calendar.SUNDAY) {
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
                }
            })
            update_texts();
        }
    }
    fun weather_code_to_url(weather_code : Int, is_day : Boolean) : String
    {
        return when (weather_code) {

            0 -> if (is_day) "clear-day" else "clear-night"
            1 -> if (is_day) "clear-day" else "clear-night"

            2 -> if (is_day) "partly-cloudy-day" else "partly-cloudy-night"

            3 -> if (is_day) "cloudy" else "cloudy"

            45 -> if (is_day) "fog-day" else "fog-night"
            48 -> if (is_day) "haze-day" else "haze-night"

            51 -> if (is_day) "partly-cloudy-day-drizzle" else "partly-cloudy-night-drizzle"
            53 -> if (is_day) "drizzle" else "drizzle"
            55 -> if (is_day) "extreme-day-drizzle" else "extreme-night-drizzle"
            56 -> if (is_day) "overcast-drizzle" else "overcast-drizzle"
            57 -> if (is_day) "extreme-drizzle" else "extreme-drizzle"

            61 -> if (is_day) "partly-cloudy-day-rain" else "partly-cloudy-night-rain"
            63 -> if (is_day) "rain" else "rain"
            65 -> if (is_day) "extreme-day-rain" else "extreme-night-rain"
            66 -> if (is_day) "overcast-rain" else "overcast-rain"
            67 -> if (is_day) "extreme-rain" else "extreme-rain"

            71 -> if (is_day) "partly-cloudy-day-snow" else "partly-cloudy-night-snow"
            73 -> if (is_day) "snow" else "snow"
            75 -> if (is_day) "extreme-day-snow" else "extreme-night-snow"
            77 -> if (is_day) "extreme-snow" else "extreme-snow"

            80 -> if (is_day) "mostly-clear-day-rain" else "mostly-clear-night-rain"
            81 -> if (is_day) "mostly-clear-day-rain" else "mostly-clear-night-rain"
            82 -> if (is_day) "extreme-day-rain" else "extreme-night-rain"

            85 -> if (is_day) "mostly-clear-day-snow" else "mostly-clear-night-snow"
            86 -> if (is_day) "mostly-clear-day-snow" else "mostly-clear-night-snow"

            95 -> if (is_day) "thunderstorms-day" else "thunderstorms-night"
            96 -> if (is_day) "thunderstorms-day-hail" else "thunderstorms-night-hail"
            99 -> if (is_day) "thunderstorms-extreme-day-hail" else "thunderstorms-extreme-night-hail"

            else -> ""
        }
    }
    fun load_weather_days(obj : JSONObject)
    {
        var daily = obj.getJSONObject("daily");
        var current = obj.getJSONObject("current");
        var time = daily.getJSONArray("time");
        var wcode = daily.getJSONArray("weather_code");
        var atemp_max = daily.getJSONArray("apparent_temperature_max");
        var atemp_min = daily.getJSONArray("apparent_temperature_min");
        var rain_s = daily.getJSONArray("rain_sum");

        var hash_v = Hashtable<Int, Drawable>();

        for(i in 0 until time.length())
        {
            var tm = time.getLong(i);
            var day = Date(tm*1000);
            var greg = GregorianCalendar();
            greg.time = day;
            val day_idx : Int = when(greg.get(Calendar.DAY_OF_WEEK))
            {
                Calendar.SUNDAY -> 6;
                else -> {
                    greg.get((Calendar.DAY_OF_WEEK))-2;
                }
            }

            Log.println(Log.DEBUG, "tg", "day_idx: ${day_idx}, ${greg.get(Calendar.DAY_OF_WEEK)}, ${tm}, ${day.day}");

            var weather_code = wcode.getInt(i);
            var temp_min = atemp_min.getDouble(i);
            var temp_max = atemp_max.getDouble(i);
            var rains = rain_s.getDouble(i);
            var is_day = true;
            var bitmap : Drawable? = null;

            if(greg.get(Calendar.DAY_OF_WEEK)==(GregorianCalendar()).get(Calendar.DAY_OF_WEEK))
                is_day = current.getInt("is_day") != 0;

            if(hash_v[weather_code + (if (is_day) (256) else (0))] != null)
                bitmap = hash_v[weather_code + (if (is_day) (256) else (0))]!!;

            if(bitmap == null)
            {
                val icon: String = weather_code_to_url(weather_code, is_day)
                val url = "cdn.meteocons.com/3.0.0-next.10/svg-static/fill/${icon}.svg";
                val aurl = URL(
                    "https", url.split("/")[0], 443, url.split("/").stream().skip(1).collect(
                        Collectors.joining("/")
                    )
                );

                with(aurl.openConnection() as HttpsURLConnection)
                {
                    setRequestProperty("User-Agent", "curl/7.81.0");
                    Log.println(Log.DEBUG, "tag", "svg: ${url}, ${responseMessage}");

                    var svg = SVG.getFromInputStream(getInputStream());
                    bitmap = PictureDrawable(svg.renderToPicture());
                    //var bm_img: Bitmap = SVg.decodeStream(getInputStream());
                    //bitmap = bm_img;
                    //Log.println(Log.DEBUG, "tag", "dw: ${bitmap}");
                    hash_v[weather_code + (if (is_day) (256) else (0))] = bitmap!!;
                }
                Log.println(Log.DEBUG, "tag","weather_code: ${weather_code}, url: ${url}");
            }

            wdays[day_idx] = weather_day(temp_min, temp_max, bitmap!!, rains, is_day,greg.get(Calendar.DAY_OF_WEEK)==(GregorianCalendar()).get(Calendar.DAY_OF_WEEK));
        }

    }
    data class fuck_you_kotlin(var d : Double);
    fun get_long_lat_ip(long : fuck_you_kotlin, lat : fuck_you_kotlin)
    {
        Log.println(Log.DEBUG, "tg", "USING LONG_LAT_IP");
        var sb : StringBuilder = StringBuilder();
        var url = URL("https", "ipinfo.io", 443, "");
        with(url.openConnection() as HttpsURLConnection)
        {
            setRequestProperty("User-Agent", "curl/7.81.0");
            val reader = getInputStream().bufferedReader();
            var line: String = reader.readText();
            sb.append(line);
        }
        var str_res = sb.toString();
        var json = JSONObject(str_res);

        val loc = json.getString("loc");
        val loc_s = loc.split(",");
        val longitude = loc_s[1].toDouble();
        val latitude = loc_s[0].toDouble();

        long.d = longitude;
        lat.d = latitude;
    }
    fun get_long_lat_net(long : fuck_you_kotlin, lat : fuck_you_kotlin) : Boolean
    {
        if(checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED)
        {
            requestPermissions(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION), 0);
            if(checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED)
                return false;
        }
        val lm : LocationManager = getSystemService(LOCATION_SERVICE) as LocationManager;
        var location: Location? = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
        if(location == null) {
            val s = Semaphore(0);
            fusedLocationClient = LocationServices.getFusedLocationProviderClient(this);
            fusedLocationClient!!.lastLocation.addOnSuccessListener { loc ->
                location = loc;
                s.release();
            };
            s.tryAcquire(1000, TimeUnit.MILLISECONDS);
            if(location == null)
                return false;
        }
        long.d = location.longitude;
        lat.d = location.latitude;
        return true;
    }
    fun load_weather(cont : () -> Unit)
    {
        // haha fuck your location settings
        var th = thread(isDaemon = true) {
            var sb : StringBuilder = StringBuilder();
            try {
                Looper.prepare();
                var url : URL;
                var str_res : String;
                var json : JSONObject;
                var latd : fuck_you_kotlin = fuck_you_kotlin(0.0);
                var longd : fuck_you_kotlin = fuck_you_kotlin(0.0);
                var latitude : Double;
                var longitude : Double;
                if(!get_long_lat_net(longd, latd))
                    get_long_lat_ip(longd, latd);
                latitude = latd.d;
                longitude = longd.d;

                val gc : GregorianCalendar = GregorianCalendar();
                gc.set(Calendar.DAY_OF_WEEK, Calendar.MONDAY);

                var sdfm : SimpleDateFormat = SimpleDateFormat("yyyy-MM-dd")
                var sbeg = sdfm.format(gc.time);

                gc.set(Calendar.DAY_OF_WEEK, Calendar.SUNDAY);
                gc.add(Calendar.WEEK_OF_YEAR, 1);
                var send = sdfm.format(gc.time);

                url = URL("https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&daily=weather_code,apparent_temperature_max,apparent_temperature_min,rain_sum&current=is_day&timezone=auto&timeformat=unixtime&start_date=${sbeg}&end_date=${send}");
                Log.println(Log.DEBUG, "tg", "url: ${url.toURI()}");
                with(url.openConnection() as HttpsURLConnection)
                {
                    setRequestProperty("User-Agent", "curl/7.81.0");
                    val reader = getInputStream().bufferedReader();
                    var line: String = reader.readText();
                    sb.append(line);
                }

                str_res = sb.toString();

                json = JSONObject(str_res);

                load_weather_days(json);


                //Log.println(Log.DEBUG, "tag", "weather data: ${str_res}");
            }
            catch(e : Exception)
            {
                Log.println(Log.DEBUG, "except", "${e.printStackTrace()}");
            }
            cont();
        }
    }
    fun continue_timetable()
    {
        runOnUiThread {
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
            } catch (e: Exception) {
                Log.println(Log.DEBUG, "dbge", e.toString());
            }
        }
    }
    fun load_timetable()
    {
        if(lbody == null)
            return;

        runOnUiThread{

            web_view!!.webViewClient = WebViewClient();
            val d = findViewById<ConstraintLayout>(R.id.main)
            d.removeView(web_view!!);
            web_view!!.clearHistory();
            web_view!!.clearCache(true);
            web_view!!.loadUrl("about:blank");
            web_view!!.onPause();
            web_view!!.removeAllViews();
            web_view!!.destroyDrawingCache();
            web_view!!.pauseTimers();
            web_view!!.destroy();

            init_login();

            load_weather(::continue_timetable);
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

        /*

        var webview = findViewById<WebView>(R.id.web2);

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
    fun load_webview()
    {
        setContentView(R.layout.activity_focus_get)
        web_view = findViewById<WebView>(R.id.web);
        web_view!!.alpha = 1.0f;

        web_view!!.settings.javaScriptEnabled = true;
        web_view!!.settings.domStorageEnabled = true;

        var url_target = "https://focus.barton.ac.uk";

        web_view!!.addJavascriptInterface(focus_inject(this), "AndroidFocusInjection");

        web_view!!.webViewClient = object : WebViewClient()
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
            override fun onPageFinished(view : WebView?, url : String?)
            {
                super.onPageFinished(view, url);
                if(url == null)
                    return;
                if(!url.contains("home") || !url.contains("focus"))
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

                /*if(url != "https://focus.barton.ac.uk/login")
                {
                    var cookies_ = CookieManager.getInstance().getCookie(url);
                    if(cookies_ != null && cookies_.contains("session"))
                    {
                        cookies = cookies_;
                        webview.visibility = View.GONE;
                        Log.println(Log.DEBUG, "dbg", "page finished $url");
                        finish_login();
                    }
                }*/
            }
        }
        web_view!!.loadUrl(url_target);
    }
    @SuppressLint("ClickableViewAccessibility")
    fun continue_cache()
    {
        runOnUiThread {
            update_weather_day();
            var tview = findViewById<TextView>(R.id.view7);
            var button2 = findViewById<Button>(R.id.button2);
            var button1 = findViewById<Button>(R.id.button);
            var button3 = findViewById<Button>(R.id.button3);
            var dm = date.get(Calendar.DAY_OF_MONTH);
            var scv = findViewById<ScrollView>(R.id.scroll_view);
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
                if(date.get(Calendar.DAY_OF_WEEK) != Calendar.MONDAY) {
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
            }
            button1.setOnClickListener {
                if(date.get(Calendar.DAY_OF_WEEK) != Calendar.SUNDAY) {
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
            scv.setOnTouchListener(object : gesture_swipe(this) {
                override fun onSwipeRight() {
                    if(date.get(Calendar.DAY_OF_WEEK) != Calendar.MONDAY) {
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
                }

                override fun onDoubleClick() {
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

                override fun onSwipeLeft() {
                    if(date.get(Calendar.DAY_OF_WEEK) != Calendar.SUNDAY) {
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
                }
            })
            update_texts();

        }
    }
    fun load_cache(week: week_cached?) : Boolean
    {
        if(week == null) {
            load_webview();
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

        load_weather(::continue_cache);
        return true;
    }
    fun do_login()
    {
        val calendar = Calendar.getInstance(Locale.getDefault())
        val firstDayInt = calendar.getFirstDayOfWeek()

        var gcur = GregorianCalendar();
        var week_id = gcur.get(Calendar.WEEK_OF_YEAR);
        if(gcur.get(Calendar.DAY_OF_WEEK) == Calendar.SUNDAY && firstDayInt == Calendar.SUNDAY)
            week_id--;
        var has_data = false;
        cache_view?.all_weeks?.observe(this) {
            caches_week -> has_data = load_cache(caches_week.find {
                it.week_id == week_id
            })
        };
        //if(has_data)
            return;


    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cache_view = ViewModelProvider(this)[week_view::class.java];
        enableEdgeToEdge()
        setContentView(R.layout.activity_focus_main)
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