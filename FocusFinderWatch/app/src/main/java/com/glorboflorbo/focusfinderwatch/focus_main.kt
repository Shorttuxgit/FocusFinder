package com.glorboflorbo.focusfinderwatch

import android.annotation.SuppressLint
import android.app.Application
import android.content.ClipData
import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.content.DialogInterface
import android.content.Intent
import android.content.SharedPreferences
import android.content.UriMatcher
import android.content.res.AssetFileDescriptor
import android.database.Cursor
import android.database.MatrixCursor
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.drawable.Drawable
import android.media.MediaMetadata
import android.net.Uri
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import android.util.Base64
import android.util.Log
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.content.edit
import androidx.core.graphics.drawable.toBitmap
import androidx.core.net.toUri
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
import androidx.vectordrawable.graphics.drawable.VectorDrawableCompat
import com.google.gson.Gson
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.MultiFormatWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import com.journeyapps.barcodescanner.BarcodeEncoder
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import org.mozilla.geckoview.GeckoResult
import org.mozilla.geckoview.GeckoRuntime
import org.mozilla.geckoview.GeckoSession
import org.mozilla.geckoview.GeckoView
import org.mozilla.geckoview.StorageController
import org.mozilla.geckoview.WebExtension
import java.io.ByteArrayOutputStream
import java.lang.Integer.min
import java.math.BigInteger
import java.net.CookieManager
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.GregorianCalendar
import java.util.Locale
import java.util.concurrent.Executors
import java.util.zip.GZIPOutputStream
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.concurrent.atomics.decrementAndFetch
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

                var ts_date = (desc_sdfmt.parse(ts)!!);
                var te_date = (desc_sdfmt.parse(te)!!);

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
    @ColumnInfo val person_name : String,
    @ColumnInfo val is_main : Boolean,
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
@Database(entities = [week_cached::class], version = 2, exportSchema = false)
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
    var vtime2 : TextView;
    var vstaff : TextView;
    var vview : LinearLayout;
    var sdfmt : SimpleDateFormat = SimpleDateFormat("HH:mm");
    constructor(vt : TextView, vt2 : TextView, vr : TextView, vs : TextView, vtl : TextView, vv : LinearLayout)
    {
        vstaff = vs;
        vtitle = vtl;
        vroom = vr;
        vtime = vt;
        vtime2 = vt2;
        vview = vv;
    }
    fun set_info(ev: timetable_event)
    {
        var str_b = sdfmt.format(ev.time_start.getTime());
        var str_a = sdfmt.format(ev.time_end.getTime());

        vtime.text = str_b;
        vtime2.text = str_a;

        vroom.text = "room: ${ev.room}";
        vtitle.text = "${ev.title}";
        vstaff.text = "staff: ${ev.staff}";

        val cl = vview.context.resources.getColor(R.color.blue_dark);

        if(ev.title == "Study Period" || ev.title == "Personal Development")
            vview.setBackgroundColor(cl);
        else
            vview.setBackgroundColor(Color.TRANSPARENT);
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
    var shared_prefs : SharedPreferences? = null;
    var person_name = "";

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
    fun gen_qr_code(data : String)
    {
        setContentView(R.layout.activity_qrcode_viewer);

        val ex = findViewById<Button>(R.id.exit_2);
        ex.setOnClickListener {
            init_view_login();
            ui_timetable();
        }
        var bc = MultiFormatWriter();
        try {

            val hints = mapOf(
                EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
                EncodeHintType.MARGIN to 0
            )
            val bm = bc.encode(data, BarcodeFormat.QR_CODE, 0, 0, hints);

            val rec = bm.enclosingRectangle;
            val b_left = rec[0];
            val b_top = rec[1];
            val b_width = rec[2];
            val b_height = rec[3];

            //Log.println(Log.DEBUG, "ltwh", "$b_left $b_top $b_width $b_height");

            val dw : Drawable = object : Drawable()
            {
                private val black_paint: Paint = Paint().apply { setARGB(255, 0, 0, 0) }
                private val white_paint: Paint = Paint().apply { setARGB(255, 255, 255, 255) }
                private val debug_paint: Paint = Paint().apply { setARGB(255, 0, 255, 0) }
                override fun draw(p0: Canvas) {
                    val width: Int = bounds.width()
                    val height: Int = bounds.height()
                    val offx = width.coerceAtMost(height).toFloat() / (b_width+20);
                    val offy = width.coerceAtMost(height).toFloat() / (b_height+20);

                    val mx = (width.toFloat() - offx*(b_width+20))/(2*offx);
                    val my = (height.toFloat() - offy*(b_height+20))/(2*offy);
                    Log.println(Log.DEBUG, "wh", "$width v $height");
                    p0.drawRect(mx*offx, my*offy, offx*(b_width+mx+20), offy*(b_height+my+20), white_paint);

                    for(y in 0 until b_height)
                    {
                        for(x in 0 until b_width)
                        {
                            val bit = bm.get(x+b_left, y+b_top);
                            if(bit)
                                p0.drawRect((x+10+mx)*offx, (y+10+my)*offy, (x+11+mx)*offx, (y+11+my)*offy, black_paint);
                            //p0.drawCircle(x * off, y * off, radius, black_paint);
                        }
                    }
                }

                @Deprecated("Deprecated in Java")
                override fun getOpacity(): Int {
                    return PixelFormat.OPAQUE;
                }

                override fun setAlpha(p0: Int) {

                }

                override fun setColorFilter(p0: ColorFilter?) {

                }

            }
            //val bitmap = bc.encodeBitmap(data, BarcodeFormat.QR_CODE, 150, 150, hints);
            val iv = findViewById<ImageView>(R.id.qr_code);
            iv.setImageDrawable(dw);
        } catch(e : Exception)
        {


        }
    }
    fun do_share()
    {
        var weekd = nulltimetable_day;

        var final = StringBuilder();
        final.append(date.timeInMillis/1000/60/60/24);
        final.append("^");
        final.append(person_name);
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

        gen_qr_code(output);

        //var cp : ClipData = ClipData.newPlainText("Timetable Share", output);
        Log.println(Log.DEBUG, "tg", "compressed day:   ${output}");
        Log.println(Log.DEBUG, "tg", "uncompressed day: ${final.toString()}");
    }
    @SuppressLint("ClickableViewAccessibility")
    fun ui_timetable()
    {
        runOnUiThread {
            var tview = findViewById<TextView>(R.id.view7);
            val scv = findViewById<ScrollView>(R.id.scroll_view);
            var exit = findViewById<Button>(R.id.exit);
            var shareb = findViewById<Button>(R.id.share);
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
            exit.setOnClickListener {
                finishAndRemoveTask();
                android.os.Process.killProcess(android.os.Process.myPid());
            }
            shareb.setOnClickListener {
                do_share();
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

        var week_id = g.get(Calendar.WEEK_OF_YEAR);
        val calendar = Calendar.getInstance(Locale.getDefault())
        val firstDayInt = calendar.getFirstDayOfWeek()
        if(g.get(Calendar.DAY_OF_WEEK) == Calendar.SUNDAY && firstDayInt == Calendar.SUNDAY)
            week_id--;

        var cache_save = week_cached(week_id, person_name, true, wlist);

        cache_view?.insert(cache_save);
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
    fun init_view_login()
    {
        setContentView(R.layout.activity_focus_main);

        views[0] = timetable_view(findViewById<TextView>(R.id.v1time), findViewById<TextView>(R.id.v1time2), findViewById<TextView>(R.id.v1room), findViewById<TextView>(R.id.v1staff), findViewById<TextView>(R.id.v1title), findViewById<LinearLayout>(R.id.v1view));
        views[1] = timetable_view(findViewById<TextView>(R.id.v2time), findViewById<TextView>(R.id.v2time2), findViewById<TextView>(R.id.v2room), findViewById<TextView>(R.id.v2staff), findViewById<TextView>(R.id.v2title), findViewById<LinearLayout>(R.id.v2view));
        views[2] = timetable_view(findViewById<TextView>(R.id.v3time), findViewById<TextView>(R.id.v3time2), findViewById<TextView>(R.id.v3room), findViewById<TextView>(R.id.v3staff), findViewById<TextView>(R.id.v3title), findViewById<LinearLayout>(R.id.v3view));
        views[3] = timetable_view(findViewById<TextView>(R.id.v4time), findViewById<TextView>(R.id.v4time2), findViewById<TextView>(R.id.v4room), findViewById<TextView>(R.id.v4staff), findViewById<TextView>(R.id.v4title), findViewById<LinearLayout>(R.id.v4view));
    }
    fun init_login()
    {
        init_view_login();

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
    fun load_password()
    {
        setContentView(R.layout.activity_password);
        val pass = findViewById<EditText>(R.id.editTextText2);

        val user = findViewById<EditText>(R.id.editTextText);

        val bsk = findViewById<Button>(R.id.button);
        bsk.setOnClickListener {
            AlertDialog.Builder(this).setTitle("Confirmation")
                .setMessage("Are you sure you would like to skip?")
                .setPositiveButton(android.R.string.ok, object : DialogInterface.OnClickListener {
                    override fun onClick(p0: DialogInterface?, p1: Int) {
                        load_gecko(true);
                        //name = shared_prefs?.getString("user_name", null);
                        //pass = shared_prefs?.getString("user_password", null);
                    }

                }).setNegativeButton(android.R.string.cancel, null).show();
        }

        val but = findViewById<Button>(R.id.button7);
        but.setOnClickListener {
            var passw = pass.text.toString();
            var usern = user.text.toString();

            if(usern.length <= 0) {
                AlertDialog.Builder(this).setTitle("Invalid input")
                    .setMessage("Email length must be greater than 0")
                    .setPositiveButton(android.R.string.ok, null).show();
                return@setOnClickListener
            }
            val bo = usern.endsWith("@barton.ac.uk", true);
            if(!bo)
            {
                AlertDialog.Builder(this).setTitle("Invalid input")
                    .setMessage("Email address must end with @barton.ac.uk domain")
                    .setPositiveButton(android.R.string.ok, null).show();
                return@setOnClickListener
            }

            if(passw.length <= 0) {
                AlertDialog.Builder(this).setTitle("Invalid input")
                    .setMessage("Password length must be greater than 0")
                    .setPositiveButton(android.R.string.ok, null).show();
                return@setOnClickListener
            }

            val ptext = if(passw.length <= 2) passw else "${passw[0]}${"*".repeat(passw.length-2)}${passw[passw.length-1]}";
            AlertDialog.Builder(this).setTitle("Confirmation")
                .setMessage("Are you sure the email address ${usern} and password ${ptext} length ${passw.length} are correct?")
                .setPositiveButton(android.R.string.ok, object : DialogInterface.OnClickListener {
                    override fun onClick(p0: DialogInterface?, p1: Int) {
                        with(shared_prefs?.edit()!!)
                        {
                            putString("user_name", usern);
                            putString("user_password", passw);
                            apply();
                        }
                        load_gecko(false);
                        //name = shared_prefs?.getString("user_name", null);
                        //pass = shared_prefs?.getString("user_password", null);
                    }

                }).setNegativeButton(android.R.string.cancel, null).show();
        }

        val x_ex = findViewById<Button>(R.id.button8)
        x_ex.setOnClickListener {
            finishAndRemoveTask();
            android.os.Process.killProcess(android.os.Process.myPid());
        }
    }
    var gecko_port : WebExtension.Port? = null;
    @OptIn(ExperimentalAtomicApi::class)
    fun load_gecko(skip_pass : Boolean)
    {
        var name : String? = "";
        var pass : String? = "";
        if(!skip_pass) {
            name = shared_prefs?.getString("user_name", null);
            pass = shared_prefs?.getString("user_password", null);
            if (name == null || pass == null)
                return load_password();
        }

        setContentView(R.layout.activity_focus_get);

        val x_ex = findViewById<Button>(R.id.button6);
        x_ex.setOnClickListener {
            finishAndRemoveTask();
            android.os.Process.killProcess(android.os.Process.myPid());
        }

        val WQHYFFSDYHIASADS = findViewById<Button>(R.id.button4);
        WQHYFFSDYHIASADS.visibility = View.GONE;

        var gecko_view : GeckoView = findViewById<GeckoView>(R.id.geckoview);

        var gecko_session : GeckoSession = GeckoSession();

        var gecko_runtime : GeckoRuntime = GeckoRuntime.create(this);
        gecko_runtime.settings.consoleOutputEnabled = true;
        //gecko_session.loadUri("https://focus.barton.ac.uk");
        gecko_session.settings.allowJavascript = true;


        val port_delegate = object : WebExtension.PortDelegate {
            override fun onPortMessage(message: Any, port: WebExtension.Port) {
                super.onPortMessage(message, port)

                if(port == gecko_port)
                {
                    person_name = message.toString().removePrefix("Welcome Back, ").replace("\n", "").trim();
                    Log.println(Log.DEBUG, "rec", "person_name : $person_name");
                }
                else
                {
                    lbody = message.toString();

                    runOnUiThread {
                        gecko_view.let {
                            gecko_view.releaseSession()?.close();
                        };
                        gecko_session.close();

                        init_login();

                        Log.println(Log.DEBUG, "tag", "lbody: ${lbody}");

                        load_timetable();
                    }
                }
            }

            override fun onDisconnect(port: WebExtension.Port) {
                super.onDisconnect(port)
                if(gecko_port == port)
                    gecko_port = null;
            }
        }

        val message_delegate = object : WebExtension.MessageDelegate {
            override fun onConnect(port: WebExtension.Port) {
                super.onConnect(port);
                Log.println(Log.DEBUG, "ttt", "onConnect ${port.name} ${port.sender.webExtension.id}");
                if(port.sender.webExtension.id == "passwd@slungomatic.com" && !skip_pass) {
                    gecko_port = port;
                    Log.println(Log.DEBUG, "got pwd", "paswd");
                    val message = JSONObject()
                    message.put("username", "$name");
                    message.put("password", "$pass");

                    port.postMessage(message);
                }
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
                val atomic_cnt = AtomicInt(2);
                gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/bingus/", "inject@slungomatic.com").accept {
                    ext -> ext?.setMessageDelegate(message_delegate, "browser");
                    if(atomic_cnt.decrementAndFetch() <= 0) {
                        continue_login(gecko_runtime, gecko_session, gecko_view);
                    }
                }
                gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/read_data/", "passwd@slungomatic.com").accept {
                    ext -> ext?.setMessageDelegate(message_delegate, "browser");
                    if(atomic_cnt.decrementAndFetch() <= 0) {
                        continue_login(gecko_runtime, gecko_session, gecko_view);
                    }
                }
            }
            else
            {
                val uninstallTasks = builtInExtensions.map { extension ->
                    gecko_runtime.webExtensionController.uninstall(extension)
                }
                GeckoResult.allOf(uninstallTasks).accept {
                    val atomic_cnt = AtomicInt(2);
                    gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/bingus/", "inject@slungomatic.com").accept {
                            ext -> ext?.setMessageDelegate(message_delegate, "browser");
                        if(atomic_cnt.decrementAndFetch() <= 0) {
                            continue_login(gecko_runtime, gecko_session, gecko_view);
                        }
                    }
                    gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/read_data/", "passwd@slungomatic.com").accept {
                            ext -> ext?.setMessageDelegate(message_delegate, "browser");
                        if(atomic_cnt.decrementAndFetch() <= 0) {
                            continue_login(gecko_runtime, gecko_session, gecko_view);
                        }
                    }
                    /*gecko_runtime.webExtensionController.ensureBuiltIn("resource://android/assets/fuckingwork/", "inject@slungomatic.com")
                        .accept { extension -> extension?.setMessageDelegate(message_delegate, "browser");continue_login(gecko_runtime, gecko_session, gecko_view);
                        };*/
                }
            }
        }
    }
    @SuppressLint("ClickableViewAccessibility")
    fun load_cache(week: week_cached?) : Boolean
    {
        Log.println(Log.DEBUG, "tg", "week: ${week}");
        if(week == null) {
            load_gecko(false);
            return false;
        }
        init_login();

        person_name = week.person_name;

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

        ui_timetable();
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
        AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES);
        cache_view = ViewModelProvider(this)[week_view::class.java];
        shared_prefs = this.getPreferences(Context.MODE_PRIVATE);
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