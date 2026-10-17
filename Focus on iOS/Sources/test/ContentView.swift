import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 10) {

                Text("Six Words to describe me")
                    .bold()
                    .padding()
                    .background(Color.green, in: RoundedRectangle(cornerRadius: 10))
                Text("Programming")
                    .bold()
                    .padding()
                    .background(Color.blue, in: RoundedRectangle(cornerRadius: 10))

            HStack(spacing: 10){
                Text("This is")
                    .bold()
                    .padding()
                    .background(Color.blue, in: RoundedRectangle(cornerRadius: 10))
                Text("Programming")
                    .bold()
                    .padding()
                    .background(Color.teal, in: RoundedRectangle(cornerRadius: 10))                        
                    }
            

                

          
        }

    }
}