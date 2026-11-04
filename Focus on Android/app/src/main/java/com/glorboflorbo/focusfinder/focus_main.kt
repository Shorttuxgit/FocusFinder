package com.glorboflorbo.focusfinder

import android.Manifest
import android.annotation.SuppressLint
import android.app.Application
import android.content.ClipData
import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.UriMatcher
import android.content.pm.PackageManager
import android.content.res.AssetFileDescriptor
import android.database.Cursor
import android.database.MatrixCursor
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.drawable.Drawable
import android.graphics.drawable.PictureDrawable
import android.location.Location
import android.location.LocationManager
import android.media.MediaMetadata
import android.net.Uri
import android.os.Bundle
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import android.util.Log
import android.view.GestureDetector
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.AdapterView
import android.widget.AdapterView.OnItemSelectedListener
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.constraintlayout.widget.ConstraintLayout
import androidx.core.graphics.drawable.toBitmap
import androidx.core.net.toUri
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.Observer
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.recyclerview.widget.DividerItemDecoration
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
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
import androidx.room.concurrent.AtomicBoolean
import androidx.vectordrawable.graphics.drawable.VectorDrawableCompat
import com.caverock.androidsvg.SVG
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationServices
import com.google.gson.Gson
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.lang.Integer.min
import java.math.BigInteger
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.GregorianCalendar
import java.util.Hashtable
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.stream.Collectors
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream
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
    constructor(day : timetable_day, dow : Int)
    {
        day_of_week = dow;
        for(i in 0 until 4)
            events[i] = day.events[i];
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
    fun describe_cmpr() : String
    {
        var se : String = "";
        for(i in 0 until 4)
        {
            var ev = events[i]!!;
            var str_b = desc_sdfmt.format(ev.time_start.getTime());
            var str_a = desc_sdfmt.format(ev.time_end.getTime());
            var s : String;
            if(ev.title == "Personal Development" || ev.title == "Study Period")
                s = "${str_b}@${str_a}@${ev.title};";
            else
                s = "${str_b}@${str_a}@${ev.title}@${ev.room}@${ev.staff};";
            se += s;
        }
        return se;
    }
    fun interpret_cmpr(s : String)
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

                var room : String;
                var staff : String;
                if(title == "Personal Development" || title == "Study Period")
                {
                    room = "—";
                    staff = "—";
                }
                else
                {
                    room = data[3];
                    staff = data[4];
                }

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
    @ColumnInfo val week_id : Int,
    @ColumnInfo val day_cached : Long,
    @ColumnInfo val name : String,
    @ColumnInfo val is_main : Boolean,
    @ColumnInfo val week_days : week_day_list,
)
{
    @PrimaryKey(autoGenerate = true) var cache_id : Int = 0;
}

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
    @Query("DELETE FROM week_cached WHERE name = :name AND is_main = 0")
    suspend fun delete_of(name : String);
}
@TypeConverters(value = [week_list_converter::class])
@Database(entities = [week_cached::class], version = 6, exportSchema = false)
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
                val instance = Room.databaseBuilder(ctx.applicationContext, week_database::class.java, "week_database").fallbackToDestructiveMigration().build();
                INSTANCE = instance;
                instance;
            }
        }
    }
}

class week_repo(private val dao : week_dao)
{
    val weeks = dao.get_all();
    suspend fun insert(todo: week_cached) = dao.insert_week(todo);
    suspend fun delete_all() = dao.delete_all();
    suspend fun delete_week(week : week_cached) = dao.delete_week(week);
    suspend fun delete_of(name : String) = dao.delete_of(name);
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
    fun delete(week : week_cached) = viewModelScope.launch {
        caches.delete_week(week);
    }
    fun delete_of(name : String) = viewModelScope.launch {
        caches.delete_of(name);
    }
}
class timetable_adapter : RecyclerView.Adapter<timetable_adapter.ViewHolder>
{
    var infl : LayoutInflater;
    var ctx : Context;
    var list : ArrayList<String> = ArrayList<String>();
    constructor(c : Context)
    {
        ctx = c;
        infl = LayoutInflater.from(ctx);
    }

    override fun onCreateViewHolder(
        parent: ViewGroup,
        viewType: Int
    ): ViewHolder {
        val vw = infl.inflate(R.layout.string_layout, parent, false);
        return ViewHolder(vw);
    }

    override fun onBindViewHolder(
        holder: ViewHolder,
        position: Int
    ) {
        val animal: String = list[position] + " has Free";
        holder.tv.text = animal;
    }

    override fun getItemCount(): Int {
        return list.size;
    }
    fun getItem(id: Int): String {
        return list[id] + " has Free";
    }

    inner class ViewHolder : RecyclerView.ViewHolder {
        val tv : TextView;

        constructor(iv : View) : super(iv) {
            tv = iv.findViewById<TextView>(R.id.text_str);
        }
    }

}
class timetable_view
{
    var vtitle : TextView;
    var vroom : TextView;
    var vtime : TextView;
    var vstaff : TextView;
    var layout : LinearLayout;
    var rec : RecyclerView;
    var adapt : timetable_adapter;
    var sdfmt : SimpleDateFormat = SimpleDateFormat("HH:mm");
    constructor(vt : TextView, vr : TextView, vs : TextView, vtl : TextView, l : LinearLayout, r : RecyclerView)
    {
        vstaff = vs;
        vtitle = vtl;
        vroom = vr;
        vtime = vt;
        layout = l;
        rec = r;
        adapt = timetable_adapter(rec.context);
        var ly : LinearLayoutManager = LinearLayoutManager(rec.context);
        rec.layoutManager = ly;
        val did = DividerItemDecoration(rec.context, ly.getOrientation());
        rec.addItemDecoration(did);
        rec.adapter = adapt;
    }
    fun set_info(ev: timetable_event, s : ArrayList<String>)
    {
        var str_b = sdfmt.format(ev.time_start.getTime());
        var str_a = sdfmt.format(ev.time_end.getTime());
        var str_c = "$str_b - $str_a";

        vtime.text = str_c;

        vroom.text = "room: ${ev.room}";
        vtitle.text = "${ev.title}";
        vstaff.text = "staff: ${ev.staff}";

        if(ev.title == "Study Period" || ev.title == "Personal Development")
            layout.setBackgroundColor(Color.argb(0xFF, 0x1E, 0x20, 0x04));
        else
            layout.setBackgroundColor(Color.TRANSPARENT);

        if(ev.title == "Study Period" || ev.title == "Personal Development")
        {
            adapt.list.clear();
            adapt.list.addAll(s);

            Log.println(Log.DEBUG, "ma", "list $s, ${s.size}");

            adapt.notifyDataSetChanged();
        }
        else
        {
            val ln = adapt.list.count();
            adapt.list.clear();
            if(ln>0)
                adapt.notifyItemRangeRemoved(0, ln);
        }
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
    @JavascriptInterface
    fun handle_user(user : String)
    {
        focus_m.person_name = user.removePrefix("Welcome Back, ");
        Log.println(Log.DEBUG, "dbg", "got username ${focus_m.person_name}");
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
var current_share : String? = null;
class focus_copy : ContentProvider()
{
    private val executor = Executors.newSingleThreadExecutor();
    var uri_matcher = UriMatcher(UriMatcher.NO_MATCH);
    override fun onCreate(): Boolean {
        uri_matcher.addURI("com.glorboflorbo.focusfinder", "friend.fff", 0);
        uri_matcher.addURI("com.glorboflorbo.focusfinder", "thumb.png", 1);
        return true;
    }

    override fun openTypedAssetFile(
        uri: Uri,
        mimeTypeFilter: String,
        opts: Bundle?
    ): AssetFileDescriptor? {
        when(mimeTypeFilter)
        {
            "*/*", "text/plain" -> {
                val c_current_share = current_share;
                if (c_current_share == null)
                    return null;

                val pcd : Array<ParcelFileDescriptor> = ParcelFileDescriptor.createPipe();
                val read_pcd = pcd[0];
                val write_pcd = pcd[1];
                executor.execute {
                    ParcelFileDescriptor.AutoCloseOutputStream(write_pcd).use { stream ->
                        stream.write(c_current_share.toByteArray(Charsets.UTF_8));
                        stream.flush();
                    }
                }
                Log.println(Log.DEBUG, "matcas", "friend.fff $uri");
                return AssetFileDescriptor(read_pcd, 0, c_current_share.length.toLong());
            }
            "image/*", "image/png" -> {
                val vec_res = VectorDrawableCompat.create(context!!.resources, R.drawable.launcher_ico, context!!.theme);
                val res = vec_res!!.toBitmap();
                Log.println(Log.DEBUG, "res", "res: $res");
                val bitmap_bytes = ByteArrayOutputStream()
                res.compress(Bitmap.CompressFormat.PNG, 100, bitmap_bytes)
                val b = bitmap_bytes.toByteArray()
                val pcd : Array<ParcelFileDescriptor> = ParcelFileDescriptor.createPipe();
                val read_pcd = pcd[0];
                val write_pcd = pcd[1];
                executor.execute {
                    ParcelFileDescriptor.AutoCloseOutputStream(write_pcd).use { stream ->
                        stream.write(b);
                        stream.flush();
                    }
                }
                Log.println(Log.DEBUG, "assets", "got AssetFileDescriptor");
                return AssetFileDescriptor(read_pcd, 0, b.size.toLong());
            }
            else -> {
                Log.println(Log.DEBUG, "unknown", "$uri, $mimeTypeFilter");
                return null;
            }
        }
    }

    override fun update(
        p0: Uri,
        p1: ContentValues?,
        p2: String?,
        p3: Array<out String?>?
    ): Int {
        return 0;
    }

    override fun query(
        p0: Uri,
        p1: Array<out String?>?,
        p2: String?,
        p3: Array<out String?>?,
        p4: String?
    ): Cursor? {
        val data : ByteArray;
        val name : String;
        when(uri_matcher.match(p0)) {
            0 -> {
                val c_current_share = current_share;
                if (c_current_share == null)
                    return null;
                data = c_current_share.toByteArray();
                name = "friend.fff";
                Log.println(Log.DEBUG, "matcq", "friend.fff $p0");
            }
            1 -> {
                val vec_res = VectorDrawableCompat.create(context!!.resources, R.drawable.launcher_ico, context!!.theme);
                val res = vec_res!!.toBitmap();
                val bitmap_bytes = ByteArrayOutputStream()
                res.compress(Bitmap.CompressFormat.PNG, 100, bitmap_bytes)
                val b = bitmap_bytes.toByteArray()
                data = b;
                name = "thumb.png";
                Log.println(Log.DEBUG, "matcq", "thumb.png $p0");
            }
            else -> {
                Log.println(Log.DEBUG, "matcq", "none $p0");
                return null;
            }
        }
        val columns = p1 ?: arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE)
        val matrixCursor = MatrixCursor(columns)
        val row = matrixCursor.newRow()
        for(col in columns)
        {
            when(col)
            {
                OpenableColumns.DISPLAY_NAME -> row.add(OpenableColumns.DISPLAY_NAME, name);
                OpenableColumns.SIZE -> row.add(OpenableColumns.SIZE, data.size);
                MediaMetadata.METADATA_KEY_DISPLAY_ICON_URI -> row.add(MediaMetadata.METADATA_KEY_DISPLAY_ICON_URI, "content://com.glorboflorbo.focusfinder/thumb.png".toUri());
                "flags" -> row.add("flags", 0);
                else -> {
                    Log.println(Log.DEBUG, "recieved", "$col");
                    row.add(col, null);
                }
            }
        }
        return matrixCursor;
    }

    override fun delete(
        p0: Uri,
        p1: String?,
        p2: Array<out String?>?
    ): Int {
        return 0;
    }

    override fun getType(p0: Uri): String {
        when(uri_matcher.match(p0))
        {
            0 -> {
                Log.println(Log.DEBUG, "got1", "$p0 uri");
                return "text/plain"
            };
            1 -> {
                Log.println(Log.DEBUG, "got2", "$p0 uri");
                return "image/png"
            };
            else -> {
                Log.println(Log.DEBUG, "got3", "$p0 uri");
                return "application/octet-stream"
            };
        }
    }

    override fun insert(p0: Uri, p1: ContentValues?): Uri? {
        return null;
    }
}
class timetable_friend
{
    var days = arrayOfNulls<timetable_day>(6);
    var person_name : String;
    var week_id : Int;
    var day_time : Long;

    constructor(name : String, wid : Int, dt : Long)
    {
        person_name = name;
        week_id = wid;
        day_time = dt;
    }
}
class focus_main : AppCompatActivity() {
    var date : GregorianCalendar = GregorianCalendar();
    var cookies : String? = null;
    var sdfmt4 : SimpleDateFormat = SimpleDateFormat("EEEE, d'th' MMMM yyyy");
    var sdfmt3 : SimpleDateFormat = SimpleDateFormat("EEEE, d'rd' MMMM yyyy");
    var sdfmt2 : SimpleDateFormat = SimpleDateFormat("EEEE, d'nd' MMMM yyyy");
    var sdfmt1 : SimpleDateFormat = SimpleDateFormat("EEEE, d'st' MMMM yyyy");
    var json_sdf : SimpleDateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    var days = arrayOfNulls<timetable_day>(6);
    var wdays = arrayOfNulls<weather_day>(7);
    var views = arrayOfNulls<timetable_view>(4);
    var lbody : String? = null;
    var web_view : WebView? = null;
    var person_name : String? = null;
    var self_person : Boolean = false;
    var nulltimetable_day : timetable_day? = null;
    var cache_view : week_view? = null;
    var fusedLocationClient: FusedLocationProviderClient? = null;
    var longt : Double = 0.0;
    var latt : Double = 0.0;
    var friends = ArrayList<timetable_friend>();
    var cur_selced = -1;
    var unloaded : AtomicBoolean = AtomicBoolean(true);
    var shared_prefs : SharedPreferences? = null;
    var weather : Boolean = true;
    var hide_friends : Boolean = false;
    val cache_observer : Observer<List<week_cached>> = Observer<List<week_cached>> { week_caches ->

        if(unloaded.getAndSet(false)) {
            friends.clear();

            val calendar = Calendar.getInstance(Locale.getDefault())
            val firstDayInt = calendar.getFirstDayOfWeek()

            var gcur = GregorianCalendar();
            var week_id = gcur.get(Calendar.WEEK_OF_YEAR);
            if (gcur.get(Calendar.DAY_OF_WEEK) == Calendar.SUNDAY && firstDayInt == Calendar.SUNDAY)
                week_id--;

            var week_day = gcur.get(Calendar.DAY_OF_YEAR);
            var hour_m = gcur.get(Calendar.HOUR_OF_DAY);
            var minu = gcur.get(Calendar.MINUTE);

            //if (hour_m < 8 || (hour_m == 8 && minu <= 45))
            //    week_day--;

            var tc : week_cached? = null;
            var t: Boolean =
                week_caches.filter { it.week_id == week_id }.map { if (load_cache(it, it.is_main)) {tc = it; true;} else false; }
                    .any { it };
            if (!t)
                load_webview();
            else if(tc != null)
            {
                init_login();
                val week = tc;
                self_person = true;
                person_name = week.name;
                cur_selced = -1;
                val udate = date;
                date = GregorianCalendar();
                date.timeInMillis = week.day_cached*24*60*60*1000;
                date.set(Calendar.DAY_OF_WEEK, udate.get(Calendar.DAY_OF_WEEK));

                for(i in 0 until 6)
                {
                    days[i] = timetable_day(nulltimetable_day!!, i);
                }
                val len = min(week.week_days.day_list.size, 6);
                for(i in 0 until len)
                {
                    val week = week.week_days.day_list[i];

                    Log.println(Log.DEBUG, "dbgp", "${week.week_day_data}")

                    days[week.week_day]?.interpret(week.week_day_data);
                }

                load_weather(::continue_cache);
            }
        }
    }
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
            val s : ArrayList<String> = ArrayList();
            Log.println(Log.DEBUG, "dbg", "$i has ${views[i]} with day ${day}");
            for(j in 0 until friends.size)
            {
                if(hide_friends)
                    break;
                if(d<0)
                    break;
                if(day?.events[i]!!.title != "Study Period" && day.events[i]!!.title != "Personal Development")
                    break;
                var gc : GregorianCalendar = GregorianCalendar();
                gc.timeInMillis = friends[j].day_time*24*60*60*1000;
                gc.set(Calendar.DAY_OF_WEEK, date.get(Calendar.DAY_OF_WEEK));
                var dt : GregorianCalendar = GregorianCalendar();
                dt.timeInMillis = (date.timeInMillis/1000/60/60/24) * 24*60*60*1000;
                //Log.println(Log.DEBUG, "ttt", "${dt.timeInMillis} ?= ${gc.timeInMillis}");
                if(gc.timeInMillis != dt.timeInMillis)
                    continue;
                var dy : timetable_day = friends[j].days[d]!!;
                if(dy.events[i]!!.title == "Study Period" || dy.events[i]!!.title == "Personal Development")
                    s += friends[j].person_name;
            }
            views[i]?.set_info(day?.events[i]!!, s);
        }
        update_weather_day();
    }
    fun update_weather_day()
    {
        var d = date.get(Calendar.DAY_OF_WEEK) - 2;
        if(d < 0)
            d = 6;
        var weekd = wdays[d];
        if(weekd == null || !weather) {
            var iview = findViewById<ImageView>(R.id.imageView);
            iview.visibility = View.GONE;
            var weahter = findViewById<TextView>(R.id.weahter);
            weahter.visibility = View.GONE;
            return;
        }
        //if(weekd.is_raining() || !weekd.is_day)
        //    AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES);
        //else
        //    AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO);
        var weahter = findViewById<TextView>(R.id.weahter);
        weahter.visibility = View.VISIBLE;
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
        sst += String.format(" (${weekd.min_temp}°C - ${weekd.max_temp}°C) at %.1f,%.1f", latt, longt);
        weahter.text = sst;
        var iview = findViewById<ImageView>(R.id.imageView);
        iview.visibility = View.VISIBLE;
        iview.setImageDrawable(weekd.wdraw);
    }
    fun decompress_94(event: String) : String
    {
        var ascii_atlas = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~";
        var sz = BigInteger("${ascii_atlas.length}");
        var bi = BigInteger("0");
        for(i in event.length-1 downTo 0 )
        {
            bi *= sz;
            bi += BigInteger("${ascii_atlas.indexOf(event[i])}");
        }
        var ba = bi.toByteArray();
        //Log.println(Log.DEBUG, "ba", "${ba.joinToString()} $bi");
        var bis : ByteArrayInputStream = ByteArrayInputStream(ba);
        var gz : GZIPInputStream = GZIPInputStream(bis);
        var res = gz.readBytes();
        gz.close();
        bis.close();
        return res.toString(Charsets.UTF_8)
    }
    fun compress_94(event : String) : String
    {
        var bos : ByteArrayOutputStream = ByteArrayOutputStream(event.length);
        var gz : GZIPOutputStream = GZIPOutputStream(bos);
        gz.write(event.toByteArray());
        gz.close();
        var ba = bos.toByteArray();
        bos.close();


        var ascii_atlas = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~";
        var output = StringBuilder();
        var bi : BigInteger = BigInteger(ba);
        //Log.println(Log.DEBUG, "ba2", "${ba.joinToString()} $bi");
        var sz = BigInteger("${ascii_atlas.length}");
        var zr = BigInteger("0");
        while(bi>zr)
        {
            var id = (bi % sz).intValueExact();
            output.append(ascii_atlas[id]);
            bi /= sz;
        }
        return output.toString();
    }
    fun do_share()
    {
        var weekd = nulltimetable_day;

        var final = StringBuilder();
        final.append(date.timeInMillis/1000/60/60/24);
        final.append("^");
        final.append(person_name!!);
        final.append("^");
        for(i in 0 until 6)
        {
            var event = days[i]!!.describe_cmpr();
            final.append(event);
            final.append("^");
        }

        var output : String = final.toString();
        for(i in 0 until 1) {
            output = compress_94(output)
        }
        current_share = output;
        val tur : Uri = "content://com.glorboflorbo.focusfinder/friend.fff".toUri();
        val sh_intent = Intent(Intent.ACTION_SEND)
        sh_intent.type = "text/plain";
        sh_intent.putExtra(Intent.EXTRA_STREAM, tur);
        sh_intent.clipData = ClipData.newRawUri("Attachment", tur);
        sh_intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

        val ci = Intent.createChooser(sh_intent, "Share via");
        ci.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(ci);
        //var cp : ClipData = ClipData.newPlainText("Timetable Share", output);
        Log.println(Log.DEBUG, "tg", "compressed day:   ${output}");
        Log.println(Log.DEBUG, "tg", "uncompressed day: ${final.toString()}");
    }
    fun settings_update()
    {
        val exb = findViewById<Button>(R.id.share3);
        exb.setOnClickListener {
            init_login_nt();
            ui_timetable();
        }
        val sh4 = findViewById<Button>(R.id.share4);
        sh4.setOnClickListener {
            cache_view?.clear_all();
            do_login();
        }
        val wbox = findViewById<CheckBox>(R.id.weather_box);
        wbox.isChecked = weather;
        wbox.setOnClickListener {
            val isc = wbox.isChecked;
            with(shared_prefs?.edit()!!)
            {
                putBoolean("weather_enabled", isc);
                apply();
            }
            weather = isc;
        }

        val fbox = findViewById<CheckBox>(R.id.checkBox2);
        fbox.isChecked = hide_friends;
        fbox.setOnClickListener {
            val isc = fbox.isChecked;
            with(shared_prefs?.edit()!!)
            {
                putBoolean("hide_friends", isc);
                apply();
            }
            hide_friends = isc;
        }
    }
    @SuppressLint("ClickableViewAccessibility")
    fun ui_timetable()
    {
        runOnUiThread {
            val tself = findViewById<TextView>(R.id.person);
            if(self_person)
                tself.text = "Your Timetable";
            else
                tself.text = "$person_name's Timetable";
            val tview = findViewById<TextView>(R.id.view7);
            val button2 = findViewById<Button>(R.id.button2);
            val button1 = findViewById<Button>(R.id.button);
            val button3 = findViewById<Button>(R.id.button3);
            var shareb = findViewById<Button>(R.id.share);
            var scv = findViewById<ScrollView>(R.id.scroll_view);
            var dm = date.get(Calendar.DAY_OF_MONTH);
            var rref = findViewById<Button>(R.id.share2);
            var spn = findViewById<Spinner>(R.id.spinner);
            var vsp = findViewById<LinearLayout>(R.id.wther);
            spn.setSelection(cur_selced+1);
            if(hide_friends)
                spn.visibility = View.GONE;
            else
                spn.visibility = View.VISIBLE;

            if(hide_friends && !weather)
                vsp.visibility = View.GONE;
            else
                vsp.visibility = View.VISIBLE;

            val items : Array<String> = Array<String>(friends.size+1, {
                if(it == 0)
                    "Your timetable";
                else
                    "${friends[it-1].person_name!!}'s timetable";
            });
            var aa = ArrayAdapter<String>(this, android.R.layout.simple_spinner_dropdown_item, items);
            spn.adapter = aa;
            spn.post {
                spn.onItemSelectedListener = object : OnItemSelectedListener {
                    override fun onItemSelected(parent: AdapterView<*>?, selc: View?, pos: Int, id: Long) {
                        if((pos-1) == cur_selced)
                            return;
                        if(pos == 0)
                            do_login();
                        else
                            load_friend_table(friends[pos-1]);
                        Log.println(Log.DEBUG, "tga", "pos: $pos");
                    }

                    override fun onNothingSelected(parent: AdapterView<*>?) {
                        return;
                    }
                }
                spn.setSelection(cur_selced+1);
            }
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
            if(cur_selced < 0)
            {
                shareb.setCompoundDrawablesWithIntrinsicBounds(android.R.drawable.ic_menu_share, 0, 0, 0);
                shareb.setOnClickListener {
                    do_share();
                }
            }
            else
            {
                shareb.setOnClickListener {
                    do_login();
                }
                shareb.setCompoundDrawablesWithIntrinsicBounds(android.R.drawable.ic_menu_close_clear_cancel, 0, 0, 0);
            }
            rref.setOnClickListener {
                setContentView(R.layout.activity_settings);
                settings_update();
            }
            //rref.setOnClickListener {
            //    cache_view?.clear_all();
            //    friends.clear();
            //    do_login();
            //}
            button2.setOnClickListener {
                if (date.get(Calendar.DAY_OF_WEEK) != Calendar.MONDAY) {
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
                if (date.get(Calendar.DAY_OF_WEEK) != Calendar.SUNDAY) {
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
                val tst = GregorianCalendar();
                date.set(Calendar.DAY_OF_WEEK, tst.get(Calendar.DAY_OF_WEEK));
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
                    if (date.get(Calendar.DAY_OF_WEEK) != Calendar.MONDAY) {
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
                    val tst = GregorianCalendar();
                    date.set(Calendar.DAY_OF_WEEK, tst.get(Calendar.DAY_OF_WEEK));
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
                    if (date.get(Calendar.DAY_OF_WEEK) != Calendar.SUNDAY) {
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
    fun update_timetable(events: JSONArray)
    {
        for(i in 0 until 6)
        {
            days[i] = timetable_day(nulltimetable_day!!, i);
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

        cur_selced = -1;
        cache_view?.clear_all();
        val udate = date;
        date = days[0]!!.events[0]!!.time_start;
        date.set(Calendar.DAY_OF_WEEK, udate.get(Calendar.DAY_OF_WEEK));

        val g : GregorianCalendar = GregorianCalendar();
        var wlist : week_day_list = week_day_list(emptyList());
        for(i in 0 until 6)
        {
            val day = days[i];
            val wd : week_day = week_day(i, day?.describe()!!);
            wlist.day_list = wlist.day_list + wd;
        }

        var day = date.timeInMillis / 1000 / 60 / 60 / 24;
        var hour_m = g.get(Calendar.HOUR_OF_DAY);
        var minu = g.get(Calendar.MINUTE);

        //if(hour_m < 8 || (hour_m == 8 && minu <= 45))
        //    day--;
        var week_id = g.get(Calendar.WEEK_OF_YEAR);
        val calendar = Calendar.getInstance(Locale.getDefault())
        val firstDayInt = calendar.getFirstDayOfWeek()
        if(g.get(Calendar.DAY_OF_WEEK) == Calendar.SUNDAY && firstDayInt == Calendar.SUNDAY)
            week_id--;
        var cache_save = week_cached(week_id, day, person_name!!, self_person, wlist);

        cache_view?.insert(cache_save);

        ui_timetable();
    }
    fun weather_code_to_url(weather_code : Int, is_day : Boolean) : String
    {
        return when (weather_code) {

            0 -> if (is_day) "CLEAR" else "CLEAR0"
            1 -> if (is_day) "PCLOUDY1" else "PCLOUDY0"

            2 -> if (is_day) "MCLOUDY1" else "MCLOUDY0"

            3 -> if (is_day) "MCLOUDY" else "MCLOUDY"

            45 -> if (is_day) "FOG1" else "FOG0"
            48 -> if (is_day) "FOG" else "FOG"

            51 -> if (is_day) "RAIN1" else "RAIN0"
            53 -> if (is_day) "RAIN" else "RAIN"
            55 -> if (is_day) "SHOWER1" else "SHOWER0"
            56 -> if (is_day) "SLEET1" else "RAIN"
            57 -> if (is_day) "SLEET1" else "SLEET0"

            61 -> if (is_day) "RAIN1" else "RAIN0"
            63 -> if (is_day) "RAIN" else "RAIN"
            65 -> if (is_day) "SHOWER1" else "SHOWER0"
            66 -> if (is_day) "SHOWER1" else "SHOWER0"
            67 -> if (is_day) "SHOWER1" else "SHOWER0"

            71 -> if (is_day) "LSNOW1" else "LSNOW0"
            73 -> if (is_day) "LSNOW" else "LSNOW"
            75 -> if (is_day) "SNOW1" else "SNOW0"
            77 -> if (is_day) "SNOW" else "SNOW"

            80 -> if (is_day) "SHOWER1" else "SHOWER0"
            81 -> if (is_day) "SHOWER1" else "SHOWER0"
            82 -> if (is_day) "SHOWER1" else "SHOWER0"

            85 -> if (is_day) "LSNOW1" else "LSNOW0"
            86 -> if (is_day) "SNOW1" else "SNOW0"

            95 -> if (is_day) "TSTORM1" else "TSTORM0"
            96 -> if (is_day) "TSHOWER1" else "TSHOWER0"
            99 -> if (is_day) "TSHOWER" else "TSHOWER"

            else -> "UNKNOWN"
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
                val url = "raw.githubusercontent.com/Grabstertv/WeatherNowIcons/refs/heads/main/SVG/${icon}.svg";
                val aurl = URL(
                    "https", url.split("/")[0], 443, url.split("/").stream().skip(1).collect(
                        Collectors.joining("/")
                    )
                );

                with(aurl.openConnection() as HttpsURLConnection)
                {
                    setRequestProperty("User-Agent", "curl/7.81.0");
                    Log.println(Log.DEBUG, "tag", "svg: ${url}, ${responseMessage}");

                    val _t = responseCode;
                    Log.println(Log.DEBUG, "lg", "code $_t for $url");

                    val line = getInputStream().bufferedReader().readText();

                    //Log.println(Log.DEBUG, "tags", "svg for $url = $line");

                    var svg = SVG.getFromString(line);
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
            val _t = responseCode;
            Log.println(Log.DEBUG, "lg", "code $_t for ipinfo.io");
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
    fun get_long_lat_fixed(long : fuck_you_kotlin, lat : fuck_you_kotlin) : Boolean
    {
        long.d = -1.3660916585283378;
        lat.d = 50.96210550753733;
        return true;
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
                if(!get_long_lat_fixed(longd, latd))
                    if(!get_long_lat_net(longd, latd))
                        get_long_lat_ip(longd, latd);
                latitude = latd.d;
                longitude = longd.d;

                longt = longitude;
                latt = latitude;

                Log.println(Log.DEBUG, "tg", "long ${longitude}, lat ${latitude}");
                val gc : GregorianCalendar = GregorianCalendar();
                gc.time = date.time;
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
                    val _t = responseCode;
                    Log.println(Log.DEBUG, "lg", "code $_t for forecast");
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

            var url_target = "https://focus.barton.ac.uk";
            val s : String = CookieManager.getInstance().getCookie(url_target);
            val sa = s.split("; ");

            for(i in 0 until sa.size)
            {
                val str = sa[i];

                val arr_eq = str.split("=");
                val cn = arr_eq[0];
                val cv = arr_eq.stream().skip(1).collect(Collectors.joining("="));

                if(cn != "focus_session")
                    continue;

                val sc = "$cn=$cv; Max-Age=2592000; HttpOnly; Secure; SameSite=Lax";
                //Log.println(Log.DEBUG, "sc", "$sc");
                CookieManager.getInstance().setCookie(url_target, sc);
            }
            //Log.println(Log.DEBUG, "cookie", s);
            CookieManager.getInstance().flush();

            web_view!!.webViewClient = WebViewClient();
            val d = findViewById<ConstraintLayout>(R.id.main)
            d.removeView(web_view!!);
            web_view!!.clearHistory();
            web_view!!.clearCache(true);
            web_view!!.loadUrl("about:blank");
            web_view!!.onPause();
            //web_view!!.removeAllViews();
            //web_view!!.destroyDrawingCache();
            web_view!!.pauseTimers();
            //web_view!!.destroy();

            self_person = true;

            init_login();

            load_weather(::continue_timetable);
        }
    }
    fun init_nullt()
    {

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
    fun init_login_nt()
    {
        setContentView(R.layout.activity_focus_main);

        //Log.println(Log.DEBUG, "tagx", "${sdfmt1.format(date.time)}");

        views[0] = timetable_view(findViewById<TextView>(R.id.v1time), findViewById<TextView>(R.id.v1room), findViewById<TextView>(R.id.v1staff), findViewById<TextView>(R.id.v1title), findViewById<LinearLayout>(R.id.l1), findViewById<RecyclerView>(R.id.rec1));
        views[1] = timetable_view(findViewById<TextView>(R.id.v2time), findViewById<TextView>(R.id.v2room), findViewById<TextView>(R.id.v2staff), findViewById<TextView>(R.id.v2title), findViewById<LinearLayout>(R.id.l2), findViewById<RecyclerView>(R.id.rec2));
        views[2] = timetable_view(findViewById<TextView>(R.id.v3time), findViewById<TextView>(R.id.v3room), findViewById<TextView>(R.id.v3staff), findViewById<TextView>(R.id.v3title), findViewById<LinearLayout>(R.id.l3), findViewById<RecyclerView>(R.id.rec3));
        views[3] = timetable_view(findViewById<TextView>(R.id.v4time), findViewById<TextView>(R.id.v4room), findViewById<TextView>(R.id.v4staff), findViewById<TextView>(R.id.v4title), findViewById<LinearLayout>(R.id.l4), findViewById<RecyclerView>(R.id.rec4));
    }
    fun init_login()
    {
        init_login_nt();
        init_nullt();
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

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web_view!!, true);

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

                view?.evaluateJavascript("(function(){try { const welcome_string = document.getElementsByClassName(\"text-3xl font-bold\")[0].textContent.trim(); AndroidFocusInjection.handle_user(welcome_string); } catch(e) {} })();", null);

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
    fun cache_friend(friend: timetable_friend)
    {
        var wlist : week_day_list = week_day_list(emptyList());
        for(i in 0 until 6)
        {
            val day = friend.days[i];
            val wd : week_day = week_day(i, day?.describe()!!);
            wlist.day_list = wlist.day_list + wd;
        }
        var week_id = friend.week_id;

        var cache_save = week_cached(week_id, friend.day_time, friend.person_name, false, wlist);

        unloaded.set(false);
        cache_view?.delete_of(friend.person_name);
        cache_view?.insert(cache_save);
    }
    fun continue_fcache()
    {
        ui_timetable();
    }
    fun continue_friend()
    {
        runOnUiThread {
            //Log.println(Log.DEBUG, "selction:", "${cur_selced+1} i ${spn.selectedItemPosition}");
            continue_fcache();
        }
    }
    @SuppressLint("ClickableViewAccessibility")
    fun continue_cache()
    {
        runOnUiThread {
            //update_weather_day();
            //Log.println(Log.DEBUG, "selction:", "${cur_selced+1} i ${spn.selectedItemPosition}");
            continue_fcache();
        }
    }
    fun load_friend_cache(week: week_cached) : timetable_friend
    {
        init_nullt();
        val name_p = week.name;
        val friend = timetable_friend(name_p, week.week_id, week.day_cached);
        for(i in 0 until 6)
        {
            friend.days[i] = timetable_day(nulltimetable_day!!, i);
        }
        val len = min(week.week_days.day_list.size, 6);
        for(i in 0 until len)
        {
            val week = week.week_days.day_list[i];

            Log.println(Log.DEBUG, "dbgp friend", "${week.week_day_data}")

            friend.days[week.week_day]?.interpret(week.week_day_data);
        }

        return friend;
    }
    fun load_friend_table(friend: timetable_friend)
    {
        init_login();
        self_person = false;
        person_name = friend.person_name;

        val greg = GregorianCalendar();
        greg.timeInMillis = friend.day_time * 24 * 60 * 60 * 1000;

        greg.set(Calendar.DAY_OF_WEEK, date.get(Calendar.DAY_OF_WEEK));
        date = greg;

        for(i in 0 until 6)
        {
            days[i] = friend.days[i];
        }
        cur_selced = friends.indexOf(friend);
        load_weather(::continue_friend);
    }
    fun load_friend_week(intent : Intent)
    {
        init_login();
        val url = intent.data;
        Log.println(Log.DEBUG, "tagg", "url: $url");

        val ois = contentResolver.openInputStream(url!!);
        val data = ois!!.bufferedReader().readText();
        Log.println(Log.DEBUG, "shr", "shared text: ${data}");
        ois.close();

        val raw_str = decompress_94(data);

        Log.println(Log.DEBUG, "shr", "Decompressed: ${raw_str}");

        try
        {
            val arr = raw_str.split("^");
            val day_id = arr[0].toLong(10);
            val name_fr = arr[1];

            self_person = false;
            person_name = name_fr;

            val day_milis = day_id*1000*60*60*24;
            val greg = GregorianCalendar();
            greg.timeInMillis = day_milis;

            greg.set(Calendar.DAY_OF_WEEK, date.get(Calendar.DAY_OF_WEEK));

            date = greg;

            for(i in 0 until 6)
            {
                days[i] = timetable_day(nulltimetable_day!!, i);
            }

            for(i in 0 until 6)
            {
                val text_d = arr[i+2];
                days[i]!!.interpret_cmpr(text_d);
            }

            val calendar = Calendar.getInstance(Locale.getDefault())
            val firstDayInt = calendar.getFirstDayOfWeek()
            var week_id = greg.get(Calendar.WEEK_OF_YEAR);
            if(greg.get(Calendar.DAY_OF_WEEK) == Calendar.SUNDAY && firstDayInt == Calendar.SUNDAY)
                week_id--;

            var day = greg.timeInMillis / 1000 / 60 / 60 / 24;
            var hour_m = greg.get(Calendar.HOUR_OF_DAY);
            var minu = greg.get(Calendar.MINUTE);

            //if(hour_m < 8 || (hour_m == 8 && minu <= 45))
            //    day--;

            val tf = timetable_friend(name_fr, week_id, day);
            for(i in 0 until 6)
                tf.days[i] = days[i];

            cache_friend(tf);
            friends.add(tf);
            cur_selced = friends.size-1;

            load_weather(::continue_friend);
        }
        catch(e : Exception)
        {
            Log.println(Log.DEBUG, "err", "err: $e, ${e.printStackTrace()}");
            return;
        }
    }
    fun load_cache(week: week_cached?, is_main : Boolean) : Boolean
    {
        Log.println(Log.DEBUG, "tag", "week: $week");
        if(week == null)
            return false;
        if(!is_main)
        {
            val friend = load_friend_cache(week);
            friends.add(friend);
            return false;
        }
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

        var week_day = gcur.get(Calendar.DAY_OF_YEAR);
        var hour_m = gcur.get(Calendar.HOUR_OF_DAY);
        var minu = gcur.get(Calendar.MINUTE);

        //if(hour_m < 8 || (hour_m == 8 && minu <= 45))
        //    week_day--;

        cur_selced = -1;
        Log.println(Log.DEBUG, "mm", "${Log.getStackTraceString(Throwable())}");
        var has_data = false;
        try {
            cache_view?.all_weeks?.removeObserver(cache_observer);
        }catch(e : Exception) {}
        unloaded.set(true);
        cache_view?.all_weeks?.observe(this, cache_observer);
        //Log.println(Log.DEBUG, "tagg", cache_view?.all_weeks?.value!!.joinToString());
        //if(has_data)
            return;


    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent);
        Log.println(Log.DEBUG, "tgv2", "${intent.data}, ${intent.action}")
        if(intent.action == Intent.ACTION_VIEW)
        {
            load_friend_week(intent);
            return;
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cache_view = ViewModelProvider(this)[week_view::class.java];
        shared_prefs = this.getPreferences(Context.MODE_PRIVATE);
        enableEdgeToEdge()

        weather = shared_prefs?.getBoolean("weather_enabled", true)!!;
        hide_friends = shared_prefs?.getBoolean("hide_friends", false)!!;

        setContentView(R.layout.activity_focus_main)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }
        Log.println(Log.DEBUG, "tgv", "$intent, ${intent.action}")
        if(intent != null && intent.action == Intent.ACTION_VIEW)
        {
            load_friend_week(intent);
            return;
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