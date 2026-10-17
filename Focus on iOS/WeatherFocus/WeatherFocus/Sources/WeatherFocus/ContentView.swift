import SwiftUI

struct ContentView: View {
    var body: some View {
        HStack{

            Forecast(day: "Mon", high: 30, low: 10)
           
            Forecast(day: "Tue", high: 30, low: 10)

        }
        .padding()
    }

}

struct Forecast: View {
    let day: String
    let high: Int
    let low: Int

    var body: some View {
         VStack {
                Text(day)
                Image(systemName: "sun.max.fill")
                    .foregroundStyle(Color.yellow)
                Text("High: \(high)")
                    .foregroundStyle(Color.green)
                Text("Low: \(low)")
                    .foregroundStyle(Color.red)

        }
    }
}


